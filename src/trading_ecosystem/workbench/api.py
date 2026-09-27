"""Same-origin local onboarding API and built UI. No execution endpoint or artifact serving."""

import base64
import binascii
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.workbench import store
from trading_ecosystem.workbench.contracts import CATALOG, CreateProject


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, engine: Engine, artifacts: Path, frontend: Path, port: int = 8785) -> None:
        self.engine, self.artifacts, self.frontend = engine, artifacts, frontend.resolve()
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    server: WorkbenchServer

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def local(self, write: bool = False) -> bool:
        hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host, origin = self.headers.get("Host"), self.headers.get("Origin")
        return bool(
            host in hosts
            and (origin is None or origin == "http://" + str(host))
            and self.headers.get("Sec-Fetch-Site", "same-origin") in {"same-origin", "none"}
            and (not write or self.headers.get("X-Workbench-Request") == "1")
        )

    def send(self, code: int, value: object) -> None:
        self.respond(code, json.dumps(value).encode(), "application/json")

    def respond(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; object-src 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if not self.local():
            self.send(403, {"error": "LOCAL_SAME_ORIGIN_REQUIRED"})
            return
        parsed = urlsplit(self.path)
        path = parsed.path
        try:
            if path == "/workbench-api/catalog" and not parsed.query:
                self.send(200, {"items": CATALOG, "endorsement": False})
                return
            if path.startswith("/workbench-api/"):
                with self.server.engine.connect() as conn:
                    if path == "/workbench-api/projects":
                        query = parse_qs(parsed.query, strict_parsing=True)
                        if set(query) - {"offset"} or any(len(v) != 1 for v in query.values()):
                            raise ValueError("INVALID_QUERY")
                        offset = int(query.get("offset", ["0"])[0])
                        if not 0 <= offset <= 100000:
                            raise ValueError("INVALID_QUERY")
                        value = store.list_projects(conn, offset, self.server.artifacts)
                    elif path.startswith("/workbench-api/projects/") and not parsed.query:
                        value = store.detail(
                            conn, self.server.artifacts, UUID(path.rsplit("/", 1)[1])
                        )
                    elif path.startswith("/workbench-api/candidates/") and not parsed.query:
                        value = store.get_candidate(conn, UUID(path.rsplit("/", 1)[1])).model_dump(
                            mode="json"
                        )
                    else:
                        self.send(404, {"error": "NOT_FOUND"})
                        return
                self.send(200, value)
                return
            if path in {"/", "/workbench", "/workbench.html"} and not parsed.query:
                file = self.server.frontend / "workbench.html"
            elif path.startswith("/assets/") and not parsed.query:
                file = (self.server.frontend / path.lstrip("/")).resolve()
                if not file.is_relative_to(self.server.frontend / "assets") or file.suffix not in {
                    ".js",
                    ".css",
                }:
                    raise ValueError("INVALID_ASSET")
            else:
                self.send(404, {"error": "NOT_FOUND"})
                return
            if not file.is_file():
                self.send(503, {"error": "UI_BUILD_UNAVAILABLE"})
                return
            self.respond(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "text/plain")
        except ValueError:
            self.send(400, {"error": "INVALID_REQUEST_OR_MISSING_RECORD"})
        except (SQLAlchemyError, OSError):
            self.send(503, {"error": "WORKBENCH_STORAGE_UNAVAILABLE"})

    def do_POST(self) -> None:
        if not self.local(write=True):
            self.send(403, {"error": "LOCAL_SAME_ORIGIN_REQUIRED"})
            return
        if self.path not in {"/workbench-api/artifacts", "/workbench-api/projects"}:
            self.send(404, {"error": "NO_EXECUTION_ENDPOINT"})
            return
        try:
            if self.headers.get("Content-Type") != "application/json" or self.headers.get(
                "Transfer-Encoding"
            ):
                raise ValueError("INVALID_CONTENT_TYPE")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 23 * 1024 * 1024:
                raise ValueError("REQUEST_TOO_LARGE")
            self.connection.settimeout(15)
            body = json.loads(self.rfile.read(length))
            with self.server.engine.begin() as conn:
                if self.path.endswith("/artifacts"):
                    if not isinstance(body, dict) or set(body) != {
                        "filename",
                        "role",
                        "data_base64",
                    }:
                        raise ValueError("INVALID_ARTIFACT")
                    if not all(isinstance(v, str) for v in body.values()):
                        raise ValueError("INVALID_ARTIFACT")
                    artifact = store.register_artifact(
                        conn,
                        self.server.artifacts,
                        body["filename"],
                        body["role"],
                        base64.b64decode(body["data_base64"], validate=True),
                    )
                    result = artifact.model_dump(mode="json")
                else:
                    project = store.create_project(
                        conn, self.server.artifacts, CreateProject.model_validate(body)
                    )
                    result = project.model_dump(mode="json")
            self.send(201, result)
        except (ValueError, binascii.Error):
            self.send(400, {"error": "INVALID_REQUEST; CHECK_METADATA_AND_ARTIFACT"})
        except (SQLAlchemyError, OSError):
            self.send(503, {"error": "WORKBENCH_STORAGE_UNAVAILABLE"})

    def do_PUT(self) -> None:
        self.send(405, {"error": "METHOD_NOT_AVAILABLE"})

    do_PATCH = do_PUT
    do_DELETE = do_PUT
