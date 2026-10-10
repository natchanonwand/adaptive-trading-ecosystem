"""Local definition/review API; every execution/OOS action is rejected and audited."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.experiments import store
from trading_ecosystem.experiments.contracts import ExperimentDefinition
from trading_ecosystem.tester.api import BaselineHandler, BaselineServer
from trading_ecosystem.tester.service import Service


class ExperimentHandler(BaselineHandler):
    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if not parsed.path.startswith("/workbench-api/experiments"):
            super().do_GET()
            return
        if not self.local():
            self.send(403, {"error": "LOCAL_SAME_ORIGIN_REQUIRED"})
            return
        try:
            with self.server.engine.connect() as conn:
                if parsed.path == "/workbench-api/experiments":
                    query = parse_qs(parsed.query, strict_parsing=True)
                    if set(query) != {"project_id"} or len(query["project_id"]) != 1:
                        raise ValueError("INVALID_QUERY")
                    value: object = {
                        "items": store.list_definitions(conn, UUID(query["project_id"][0]))
                    }
                else:
                    parts = parsed.path.split("/")
                    if len(parts) != 4 or parsed.query:
                        raise ValueError("INVALID_ROUTE")
                    value = store.detail(conn, UUID(parts[3]))
            self.send(200, value)
        except ValueError:
            self.send(400, {"error": "INVALID_EXPERIMENT_REQUEST"})
        except SQLAlchemyError:
            self.send(503, {"error": "EXPERIMENT_STORAGE_UNAVAILABLE"})

    def do_POST(self) -> None:
        if not self.path.startswith("/workbench-api/experiments"):
            super().do_POST()
            return
        if not self.local(write=True):
            self.send(403, {"error": "LOCAL_SAME_ORIGIN_REQUIRED"})
            return
        try:
            if self.headers.get("Content-Type") != "application/json" or self.headers.get(
                "Transfer-Encoding"
            ):
                raise ValueError("INVALID_CONTENT_TYPE")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 128 * 1024:
                raise ValueError("INVALID_SIZE")
            self.connection.settimeout(15)
            body = json.loads(self.rfile.read(length))
            status = 200
            with self.server.engine.begin() as conn:
                if self.path == "/workbench-api/experiments":
                    value: object = store.save(conn, ExperimentDefinition.model_validate(body))
                    status = 201
                else:
                    parts = self.path.split("/")
                    if len(parts) != 5 or body != {"confirmed": True}:
                        raise ValueError("EXPLICIT_REVIEW_CONFIRMATION_REQUIRED")
                    key, action = UUID(parts[3]), parts[4]
                    if action == "freeze":
                        value = store.freeze(conn, key)
                    elif action in {"run", "search", "unlock-oos", "relock-oos", "update"}:
                        value = store.reject_action(conn, key, action)
                        status = 409
                    else:
                        raise ValueError("INVALID_ACTION")
            # Rejections commit their audit event before returning; no run is ever created.
            self.send(status, value)
        except (ValueError, ArithmeticError):
            self.send(400, {"error": "INVALID_EXPERIMENT_DEFINITION_OR_ACTION"})
        except SQLAlchemyError:
            self.send(503, {"error": "EXPERIMENT_STORAGE_UNAVAILABLE"})


class ExperimentServer(BaselineServer):
    def __init__(
        self,
        engine: Engine,
        artifacts: Path,
        frontend: Path,
        port: int = 8785,
        root: Path = Path(".local/phase5_b"),
        service: Service | None = None,
    ) -> None:
        super().__init__(engine, artifacts, frontend, port, root, service)
        self.RequestHandlerClass = ExperimentHandler
