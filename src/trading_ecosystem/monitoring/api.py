"""Local-only GET API and durable-cursor SSE; no command or ingestion endpoint."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.monitoring.queries import TABLES, read_events, read_view


class MonitoringServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, engine: Engine, port: int = 8765) -> None:
        self.engine = engine
        self.stopping = Event()
        super().__init__(("127.0.0.1", port), Handler)

    def shutdown(self) -> None:
        self.stopping.set()
        super().shutdown()


class Handler(BaseHTTPRequestHandler):
    server: MonitoringServer

    def log_message(self, format: str, *args: Any) -> None:
        # Do not echo untrusted external comments, query strings or SQL failures.
        pass

    def _json(self, status: int, data: object) -> None:
        raw = json.dumps(data, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:
        self._json(405, {"error": "READ_ONLY_API"})

    def do_PUT(self) -> None:
        self.do_POST()

    def do_DELETE(self) -> None:
        self.do_POST()

    def do_PATCH(self) -> None:
        self.do_POST()

    def do_GET(self) -> None:
        if self.headers.get("Origin") is not None or self.headers.get("Host") not in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }:
            self._json(403, {"error": "LOCAL_CLIENT_REQUIRED"})
            return
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            if parsed.query:
                self._json(400, {"error": "INVALID_QUERY"})
                return
            try:
                with self.server.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                self._json(200, {"status": "HEALTHY", "database": "HEALTHY", "read_only": True})
            except SQLAlchemyError:
                self._json(503, {"status": "ERROR", "database": "ERROR", "read_only": True})
            return
        name = parsed.path.removeprefix("/api/v1/")
        if parsed.path != "/api/v1/" + name or name not in {*TABLES, "events", "stream"}:
            self._json(404, {"error": "NOT_FOUND"})
            return
        try:
            query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
            allowed = {"stream_id", "after", "limit"} | ({"follow"} if name == "stream" else set())
            if set(query) - allowed or any(len(v) != 1 for v in query.values()):
                raise ValueError
            stream_id = UUID(query["stream_id"][0])
            cursor = query.get("after", [self.headers.get("Last-Event-ID", "0")])[0]
            after, limit = int(cursor), int(query.get("limit", ["100"])[0])
            if after < 0 or not 1 <= limit <= 1000:
                raise ValueError
            follow = query.get("follow", ["true"])[0]
            if follow not in {"true", "false"}:
                raise ValueError
        except (ValueError, KeyError):
            self._json(400, {"error": "INVALID_QUERY"})
            return
        if name == "stream":
            self._stream(stream_id, after, limit, follow == "true")
            return
        try:
            with self.server.engine.connect() as conn:
                conn.execute(text("SET TRANSACTION READ ONLY"))
                if name == "events":
                    events = read_events(conn, stream_id, after, limit)
                    data = {
                        "stream_id": str(stream_id),
                        "items": [e.model_dump(mode="json") for e in events],
                        "next_cursor": events[-1].sequence if events else after,
                        "read_only": True,
                    }
                else:
                    data = read_view(conn, name, stream_id, after, limit)
            self._json(200, data)
        except (SQLAlchemyError, ValueError, RuntimeError):
            self._json(503, {"error": "MONITORING_DATA_UNAVAILABLE"})

    def _stream(self, stream_id: UUID, after: int, limit: int, follow: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            while not self.server.stopping.is_set():
                with self.server.engine.connect() as conn:
                    conn.execute(text("SET TRANSACTION READ ONLY"))
                    events = read_events(conn, stream_id, after, limit)
                for stored in events:
                    body = stored.model_dump_json()
                    frame = (
                        f"id: {stored.sequence}\nevent: {stored.event.event_type.value}\n"
                        f"data: {body}\n\n"
                    )
                    self.wfile.write(frame.encode("utf-8"))
                    after = stored.sequence
                if not events:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
                if not follow:
                    break
                self.server.stopping.wait(1)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (SQLAlchemyError, ValueError, RuntimeError):
            try:
                self.wfile.write(b'event: monitoring_error\ndata: {"error":"DATA_UNAVAILABLE"}\n\n')
                self.wfile.flush()
            except OSError:
                pass
