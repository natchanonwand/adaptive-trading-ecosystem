"""Serial persisted orchestration, explicit start only, no OOS execution capability."""

from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Engine, text

from trading_ecosystem.experiments import campaign_store as ledger
from trading_ecosystem.experiments import campaigns, store
from trading_ecosystem.experiments.contracts import ExperimentDefinition, digest

LOCK_KEY = 541001
TERMINAL = {"COMPLETE", "PARTIAL", "NO_ELIGIBLE_SELECTION", "BUDGET_EXHAUSTED", "CANCELLED"}


class Boundary(Protocol):
    def validate(self, definition: ExperimentDefinition) -> None: ...

    def execute(
        self,
        definition: ExperimentDefinition,
        candidate: dict[str, Any],
        run: dict[str, Any],
        deadline: datetime,
        cancelled: Event,
    ) -> tuple[str, dict[str, Any] | None]: ...

    def recover(self, run: dict[str, Any]) -> tuple[str, dict[str, Any] | None]: ...


class Runner:
    def __init__(self, engine: Engine, boundary: Boundary) -> None:
        self.engine, self.boundary = engine, boundary

    def run(self, key: UUID) -> None:
        # Session advisory lock survives per-step commits and excludes every campaign worker.
        with self.engine.connect() as owner:
            if not owner.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}
            ).scalar():
                raise ValueError("CAMPAIGN_RUNNER_BUSY")
            owner.commit()
            try:
                self._run(key)
            finally:
                owner.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
                owner.commit()

    def _run(self, key: UUID) -> None:
        with self.engine.begin() as conn:
            body = ledger.read(conn, key, True)
            if body["status"] in TERMINAL:
                return
            d = ExperimentDefinition.model_validate(body["definition"])
            store.validate_baseline(conn, d)
            self.boundary.validate(d)
            if body["started_at"] is None:
                now = datetime.now(UTC)
                body["started_at"] = now.isoformat()
                body["deadline"] = (
                    now + timedelta(seconds=d.budget.maximum_wall_seconds)
                ).isoformat()
                ledger.event(body, "EXPLICIT_START")
            body["status"] = "RUNNING"
            ledger.persist(conn, body)
        while True:
            recovered = False
            with self.engine.begin() as conn:
                body = ledger.read(conn, key, True)
                d = ExperimentDefinition.model_validate(body["definition"])
                deadline = datetime.fromisoformat(body["deadline"])
                pending = next((r for r in body["runs"] if r["status"] == "RESERVED"), None)
                if pending:
                    run = pending
                    recovered = True
                else:
                    if body["cancel_requested"] or datetime.now(UTC) >= deadline:
                        body["status"] = (
                            "CANCELLED" if body["cancel_requested"] else "BUDGET_EXHAUSTED"
                        )
                        ledger.event(body, body["status"])
                        ledger.persist(conn, body)
                        return
                    candidates = body["plan"]["candidates"]
                    development = [r for r in body["runs"] if r["purpose"] == "DEVELOPMENT"]
                    if len(development) == len(candidates) and body["selection"] is None:
                        selected, decisions = campaigns.select_development(d, development)
                        body["selection"] = {
                            "selected": selected,
                            "decisions": decisions,
                            "development_identity": digest(development),
                        }
                        body["selection_identity"] = digest(body["selection"])
                        ledger.event(
                            body,
                            "DEVELOPMENT_SELECTION_FROZEN",
                            identity=body["selection_identity"],
                        )
                        ledger.persist(conn, body)
                    purpose = "DEVELOPMENT" if body["selection"] is None else "VALIDATION"
                    eligible = (
                        candidates
                        if purpose == "DEVELOPMENT"
                        else [
                            c for c in candidates if c["identity"] in body["selection"]["selected"]
                        ]
                    )
                    done = {
                        r["configuration_identity"] for r in body["runs"] if r["purpose"] == purpose
                    }
                    candidate = next((c for c in eligible if c["identity"] not in done), None)
                    if candidate is None:
                        body["status"] = (
                            "NO_ELIGIBLE_SELECTION"
                            if not eligible
                            else "PARTIAL"
                            if any(r["status"] != "COMPLETE" for r in body["runs"])
                            else "COMPLETE"
                        )
                        ledger.event(body, body["status"])
                        ledger.persist(conn, body)
                        return
                    if body["consumed_executions"] >= d.budget.maximum_native_executions:
                        body["status"] = "BUDGET_EXHAUSTED"
                        ledger.event(body, "BUDGET_EXHAUSTED")
                        ledger.persist(conn, body)
                        return
                    split = d.split_plan.splits[0 if purpose == "DEVELOPMENT" else 1]
                    identity = digest(
                        [body["plan_identity"], candidate["identity"], split.identity]
                    )
                    run = {
                        "id": str(uuid5(NAMESPACE_URL, identity)),
                        "identity": identity,
                        "configuration_identity": candidate["identity"],
                        "purpose": purpose,
                        "split_identity": split.identity,
                        "start": str(split.start),
                        "end": str(split.end),
                        "status": "RESERVED",
                        "observation": None,
                    }
                    body["runs"].append(run)
                    body["consumed_executions"] += 1
                    ledger.event(body, "EXECUTION_RESERVED", run_id=run["id"])
                    ledger.persist(conn, body)
            candidate = next(
                c
                for c in body["plan"]["candidates"]
                if c["identity"] == run["configuration_identity"]
            )
            cancel = Event()
            # Poll cancellation with a bounded helper, without holding a database transaction.
            from threading import Thread

            stopped = Event()

            def monitor(
                stopped: Event = stopped, deadline: datetime = deadline, cancel: Event = cancel
            ) -> None:
                while not stopped.wait(0.05):
                    try:
                        with self.engine.connect() as conn:
                            requested = ledger.read(conn, key)["cancel_requested"]
                        if requested or datetime.now(UTC) >= deadline:
                            cancel.set()
                    except Exception:
                        cancel.set()  # Lost control plane fails closed for the owned run.

            watcher = Thread(target=monitor, daemon=True)
            watcher.start()
            try:
                try:
                    status, result = (
                        self.boundary.recover(run)
                        if recovered
                        else self.boundary.execute(d, candidate, run, deadline, cancel)
                    )
                except (ValueError, ArithmeticError):
                    status, result = "EXECUTION_REJECTED", None
                if status == "COMPLETE":
                    if result is None:
                        raise ValueError("MISSING_RESULT")
                    result = campaigns.observation(result)
                    if result["baseline_run_id"] != run["id"]:
                        raise ValueError("RESULT_RUN_LINK_MISMATCH")
                elif result is not None:
                    raise ValueError("FAILURE_CANNOT_HAVE_SUCCESS_METRICS")
                if status in {"RESERVED", "RUNNING", "QUEUED", "PREPARING", "PARSING"}:
                    raise RuntimeError("ACTIVE_EXECUTION_REQUIRES_OWNERSHIP_RECONCILIATION")
            except (ValueError, ArithmeticError):
                status, result = "RESULT_VALIDATION_FAILED", None
            finally:
                stopped.set()
                watcher.join(timeout=2)
            with self.engine.begin() as conn:
                body = ledger.read(conn, key, True)
                current = next(r for r in body["runs"] if r["id"] == run["id"])
                if current["status"] != "RESERVED":
                    raise ValueError("IMMUTABLE_RUN_OUTCOME")
                current.update(status=status, observation=result)
                if (
                    cancel.is_set()
                    and not body["cancel_requested"]
                    and datetime.now(UTC) < deadline
                ):
                    body["cancel_requested"] = True
                    ledger.event(body, "CONTROL_PLANE_CANCELLATION")
                ledger.event(body, "EXECUTION_RECORDED", run_id=run["id"], status=status)
                ledger.persist(conn, body)
