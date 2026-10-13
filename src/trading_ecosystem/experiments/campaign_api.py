"""Explicit local campaign actions; definition routes and OOS denials stay frozen."""

import json
from threading import Thread
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.experiments import authorization
from trading_ecosystem.experiments import campaign_store as ledger
from trading_ecosystem.experiments.api import ExperimentHandler, ExperimentServer
from trading_ecosystem.experiments.baseline_boundary import BaselineBoundary
from trading_ecosystem.experiments.campaign_runner import Runner
from trading_ecosystem.experiments.reference_contract import parse_definition


class CampaignHandler(ExperimentHandler):
    server: "CampaignServer"

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if not parsed.path.startswith("/workbench-api/campaigns"):
            super().do_GET()
            return
        if not self.local():
            self.send(403, {"error": "LOCAL_SAME_ORIGIN_REQUIRED"})
            return
        try:
            with self.server.engine.connect() as conn:
                if parsed.path == "/workbench-api/campaigns":
                    query = parse_qs(parsed.query, strict_parsing=True)
                    if set(query) != {"definition_id"} or len(query["definition_id"]) != 1:
                        raise ValueError("INVALID_QUERY")
                    value = {"items": ledger.list_for(conn, UUID(query["definition_id"][0]))}
                else:
                    parts = parsed.path.split("/")
                    if len(parts) != 4 or parsed.query:
                        raise ValueError("INVALID_ROUTE")
                    value = ledger.read(conn, UUID(parts[3]))
                items = value.get("items", [value])
                for item in items:
                    item["authorization_review"] = authorization.review(
                        conn, UUID(item["id"]), self.server.artifacts, self.server.service.root
                    )
            self.send(200, value)
        except ValueError as exc:
            self.send(400, {"error": str(exc)})
        except SQLAlchemyError:
            self.send(503, {"error": "CAMPAIGN_STORAGE_UNAVAILABLE"})

    def do_POST(self) -> None:
        if not self.path.startswith("/workbench-api/campaigns"):
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
            if not 0 < length <= 2048:
                raise ValueError("INVALID_SIZE")
            self.connection.settimeout(15)
            body = json.loads(self.rfile.read(length))
            status = 200
            if self.path == "/workbench-api/campaigns":
                if (
                    set(body) != {"definition_id", "definition_identity", "confirmed"}
                    or body["confirmed"] is not True
                ):
                    raise ValueError("EXPLICIT_PLAN_CONFIRMATION_REQUIRED")
                with self.server.engine.begin() as conn:
                    value = ledger.create(
                        conn, UUID(body["definition_id"]), body["definition_identity"]
                    )
                status = 201
            else:
                parts = self.path.split("/")
                if len(parts) != 5:
                    raise ValueError("EXPLICIT_ACTION_CONFIRMATION_REQUIRED")
                key, action = UUID(parts[3]), parts[4]
                if action == "authorize":
                    if (
                        set(body) != {"confirmed", "review_identity"}
                        or body["confirmed"] is not True
                    ):
                        raise ValueError("EXPLICIT_ACTION_CONFIRMATION_REQUIRED")
                    with self.server.engine.begin() as conn:
                        value = authorization.authorize(
                            conn,
                            key,
                            self.server.artifacts,
                            self.server.service.root,
                            body["review_identity"],
                            True,
                        )
                elif body != {"confirmed": True}:
                    raise ValueError("EXPLICIT_ACTION_CONFIRMATION_REQUIRED")
                elif action == "start":
                    self.server.start_campaign(key)
                    with self.server.engine.connect() as conn:
                        value = ledger.read(conn, key)
                else:
                    with self.server.engine.begin() as conn:
                        if action == "cancel":
                            value = ledger.cancel(conn, key)
                        else:
                            value = ledger.read(conn, key, True)
                            ledger.event(
                                value, "PROTOCOL_VIOLATION", reason="OOS_OR_UNSUPPORTED_ACTION"
                            )
                            ledger.persist(conn, value)
                            status = 409
            self.send(status, value)
        except (ValueError, ArithmeticError):
            self.send(400, {"error": "CAMPAIGN_PREREQUISITE_OR_ACTION_REJECTED"})
        except SQLAlchemyError:
            self.send(503, {"error": "CAMPAIGN_STORAGE_UNAVAILABLE"})


class CampaignServer(ExperimentServer):
    campaign_thread: Thread | None = None
    campaign_id: UUID | None = None

    def start_campaign(self, key: UUID) -> None:
        # Request handler is serialized by the existing HTTPServer.
        if self.campaign_thread is not None and self.campaign_thread.is_alive():
            raise ValueError("CAMPAIGN_RUNNER_BUSY")
        boundary = BaselineBoundary(self.service)
        with self.engine.connect() as conn:
            body = ledger.read(conn, key)
            authorization.require(conn, key, self.artifacts, self.service.root, "DEVELOPMENT")
        boundary.validate(parse_definition(body["definition"]))

        def work() -> None:
            try:
                Runner(self.engine, boundary).run(key)
            except Exception:
                # No automatic retry. Preserve the reservation for explicit resume/readback.
                with self.engine.begin() as conn:
                    current = ledger.read(conn, key, True)
                    ledger.event(current, "RUNNER_STOPPED_REQUIRES_EXPLICIT_RESUME")
                    ledger.persist(conn, current)

        self.campaign_id = key
        self.campaign_thread = Thread(target=work, daemon=True)
        self.campaign_thread.start()

    def server_close(self) -> None:
        if self.campaign_thread is not None and self.campaign_thread.is_alive():
            if self.campaign_id is not None:
                with self.engine.begin() as conn:
                    ledger.cancel(conn, self.campaign_id)
            self.campaign_thread.join(timeout=10)
        super().server_close()


def install(server: CampaignServer) -> None:
    """Install only HTTP routing, never create/start/resume a campaign at startup."""
    server.RequestHandlerClass = CampaignHandler
