"""Local, same-origin baseline endpoints; never expose native HTML or executable bytes."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.tester import readiness, store
from trading_ecosystem.tester.contracts import Configuration
from trading_ecosystem.tester.service import Busy, Service
from trading_ecosystem.workbench.api import Handler, WorkbenchServer


class BaselineServer(WorkbenchServer):
    def __init__(
        self,
        engine: Engine,
        artifacts: Path,
        frontend: Path,
        port: int = 8785,
        root: Path = Path(".local/phase5_b"),
        service: Service | None = None,
    ) -> None:
        self.service = service or Service(engine, artifacts, root)
        self.service.recover()
        super().__init__(engine, artifacts, frontend, port)
        self.RequestHandlerClass = BaselineHandler

    def server_close(self) -> None:
        self.service.close()
        super().server_close()


class BaselineHandler(Handler):
    server: BaselineServer

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if not path.startswith(("/workbench-api/baseline", "/workbench-api/projects/")):
            super().do_GET()
            return
        if not self.local():
            self.send(403, {"error": "LOCAL_SAME_ORIGIN_REQUIRED"})
            return
        try:
            with self.server.engine.connect() as conn:
                value: object
                if path.startswith("/workbench-api/projects/") and not parsed.query:
                    detail = readiness.detail(
                        conn, self.server.artifacts, UUID(path.rsplit("/", 1)[1])
                    )
                    from trading_ecosystem.tester.environment import binding_status

                    detail["research_environment"] = binding_status(
                        self.server.service.root / "terminal-binding.json",
                        detail["project"]["broker_binding"]["broker_symbol"],
                    )
                    detail["baseline_enabled"] = True
                    value = detail
                elif path == "/workbench-api/baseline-candidate-readiness":
                    from trading_ecosystem.tester.environment import TerminalBinding
                    from trading_ecosystem.tester.installed_profile import public_summary
                    from trading_ecosystem.tester.qualification import qualify

                    query = parse_qs(parsed.query, strict_parsing=True)
                    if set(query) != {"project_id", "configuration_id"} or any(
                        len(v) != 1 for v in query.values()
                    ):
                        raise ValueError("INVALID_QUERY")
                    project_id = UUID(query["project_id"][0])
                    config_id = UUID(query["configuration_id"][0])
                    project = store.project(conn, project_id)
                    root = self.server.service.root
                    pinned = TerminalBinding.model_validate_json(
                        (root / "terminal-binding.json").read_bytes()
                    )
                    value = public_summary(
                        qualify(
                            conn,
                            self.server.artifacts,
                            project_id,
                            project.candidate_id,
                            config_id,
                            pinned,
                            (root.parent / "phase5_b1e/probe").resolve(),
                            (root.parent / "phase5_b1g/workbench").resolve(),
                            uuid5(NAMESPACE_URL, f"phase5b1g:{project_id}:{config_id}"),
                            installed_profile=True,
                        )
                    )
                elif path == "/workbench-api/baseline-configurations":
                    query = parse_qs(parsed.query, strict_parsing=True)
                    if set(query) != {"project_id"} or len(query["project_id"]) != 1:
                        raise ValueError("INVALID_QUERY")
                    value = {
                        "items": readiness.list_configurations(conn, UUID(query["project_id"][0]))
                    }
                elif path.startswith("/workbench-api/baseline-configurations/"):
                    value = readiness.get_configuration(conn, UUID(path.rsplit("/", 1)[1]))
                elif path == "/workbench-api/baselines":
                    query = parse_qs(parsed.query, strict_parsing=True)
                    if set(query) != {"project_id"} or len(query["project_id"]) != 1:
                        raise ValueError("INVALID_QUERY")
                    value = {"items": store.list_runs(conn, UUID(query["project_id"][0]))}
                else:
                    pieces = path.split("/")
                    if len(pieces) != 4 or pieces[2] != "baselines" or parsed.query:
                        raise ValueError("INVALID_ROUTE")
                    run_id = UUID(pieces[3])
                    run = store.get(conn, run_id)
                    result = store.result(conn, run_id)
                    value = {
                        "run": run.model_dump(mode="json"),
                        "result": result.model_dump(mode="json") if result else None,
                    }
            self.send(200, value)
        except ValueError:
            self.send(400, {"error": "INVALID_REQUEST_OR_MISSING_RECORD"})
        except (SQLAlchemyError, OSError):
            self.send(503, {"error": "BASELINE_STORAGE_UNAVAILABLE"})

    def do_POST(self) -> None:
        if not self.path.startswith(("/workbench-api/baseline", "/workbench-api/authorization/")):
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
            if not 0 < length <= 96 * 1024:
                raise ValueError("INVALID_SIZE")
            self.connection.settimeout(15)
            body = json.loads(self.rfile.read(length))
            if self.path.startswith("/workbench-api/authorization/"):
                project_id = UUID(self.path.rsplit("/", 1)[1])
                with self.server.engine.begin() as conn:
                    record = readiness.attest(
                        conn, project_id, readiness.Authorization.model_validate(body)
                    )
                self.send(201, record.model_dump(mode="json"))
                return
            if self.path == "/workbench-api/baseline-configurations":
                with self.server.engine.begin() as conn:
                    saved = readiness.save_configuration(
                        conn,
                        self.server.artifacts,
                        readiness.BaselineConfiguration.model_validate(body),
                    )
                self.send(201, saved)
                return
            if self.path == "/workbench-api/baselines":
                config = Configuration.model_validate(body)
                with self.server.engine.begin() as conn:
                    run = store.create(conn, config)
                self.send(201, run.model_dump(mode="json"))
                return
            parts = self.path.split("/")
            if len(parts) != 5 or parts[2] != "baselines" or body != {"confirmed": True}:
                raise ValueError("EXPLICIT_CONFIRMATION_REQUIRED")
            run_id = UUID(parts[3])
            if parts[4] == "start":
                run = self.server.service.start(run_id)
            elif parts[4] == "cancel":
                run = self.server.service.cancel(run_id)
            else:
                raise ValueError("INVALID_ROUTE")
            self.send(200, run.model_dump(mode="json"))
        except Busy:
            self.send(409, {"error": "BASELINE_TESTER_BUSY"})
        except ValueError:
            # Do not reflect validation values: a rejected request may contain credentials.
            self.send(400, {"error": "INVALID_BASELINE_REQUEST; CHECK_CONFIGURATION_AND_READINESS"})
        except (SQLAlchemyError, OSError):
            self.send(503, {"error": "BASELINE_STORAGE_UNAVAILABLE"})
