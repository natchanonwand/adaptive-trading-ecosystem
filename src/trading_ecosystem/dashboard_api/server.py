"""Loopback dashboard extensions; original Monitoring API/SSE is inherited unchanged."""

from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.dashboard_api import queries
from trading_ecosystem.monitoring.api import Handler, MonitoringServer


class DashboardServer(MonitoringServer):
    def __init__(self, engine: Engine, port: int = 8765) -> None:
        super().__init__(engine, port)
        self.RequestHandlerClass = DashboardHandler


class DashboardHandler(Handler):
    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        prefix = "/api/v1/dashboard/"
        if not parsed.path.startswith(prefix):
            super().do_GET()
            return
        if self.headers.get("Origin") is not None or self.headers.get("Host") not in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }:
            self._json(403, {"error": "LOCAL_CLIENT_REQUIRED"})
            return
        name = parsed.path.removeprefix(prefix)
        if name not in {"streams", "snapshot", "history", "calendar", "trades", "positions"}:
            self._json(404, {"error": "NOT_FOUND"})
            return
        try:
            raw = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
            allowed = {"after", "limit"} if name == "streams" else {"stream_id"}
            if name in {"history", "trades", "positions"}:
                allowed |= {
                    "after",
                    "limit",
                    "start",
                    "end",
                    "symbol",
                    "strategy_id",
                    "environment",
                }
            if name == "calendar":
                allowed |= {"start", "end"}
            if set(raw) - allowed or any(len(v) != 1 for v in raw.values()):
                raise ValueError
            args = {k: v[0] for k, v in raw.items()}
            stream = UUID(args["stream_id"]) if name != "streams" else None
            limit = int(args.get("limit", "100"))
            if not 1 <= limit <= 500:
                raise ValueError
            after = int(args.get("after", "0")) if name != "streams" else 0
            stream_after = UUID(args["after"]) if name == "streams" and "after" in args else None
            if after < 0:
                raise ValueError
            if name == "calendar" or "start" in args or "end" in args:
                queries.window(args.get("start", ""), args.get("end", ""))
                if (
                    name == "calendar"
                    and (
                        queries.window(args["start"], args["end"])[1]
                        - queries.window(args["start"], args["end"])[0]
                    ).days
                    > 31
                ):
                    raise ValueError
        except (ValueError, KeyError):
            self._json(400, {"error": "INVALID_QUERY"})
            return
        try:
            with self.server.engine.connect() as conn:
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
                if name == "streams":
                    data = queries.streams(conn, stream_after, limit)
                else:
                    assert stream is not None
                    if name == "snapshot":
                        data = queries.snapshot(conn, stream)
                    elif name == "calendar":
                        data = queries.calendar(conn, stream, args["start"], args["end"])
                    else:
                        data = queries.collection(conn, stream, name, after, limit, args)
            self._json(200, data)
        except (SQLAlchemyError, ValueError, RuntimeError):
            self._json(503, {"error": "MONITORING_DATA_UNAVAILABLE"})
