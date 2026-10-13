"""Campaign handoff to the existing Phase 5B service, ownership, parser and evidence."""

from datetime import UTC, datetime
from threading import Event
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from trading_ecosystem.experiments.contracts import ExperimentDefinition
from trading_ecosystem.tester import readiness, store
from trading_ecosystem.tester.contracts import ACTIVE, State
from trading_ecosystem.tester.inputs import validate_set
from trading_ecosystem.tester.service import Service

METRICS = {
    "NET_PROFIT": "net_profit",
    "TRADE_COUNT": "total_trades",
    "PROFIT_FACTOR": "profit_factor",
}


def inputs(original: str | None, assignments: dict[str, str]) -> str:
    values: dict[str, str] = {}
    if original:
        validate_set(original)
        for line in original.splitlines():
            if not line.strip() or line.startswith(";"):
                continue
            key, value = line.split("=", 1)
            if key in values:
                raise ValueError("DUPLICATE_BASELINE_INPUT")
            values[key] = value
    for key, value in assignments.items():
        if any(c in value for c in ("\r", "\n", "\x00")) or "||" in value:
            raise ValueError("INVALID_PARAMETER_ASSIGNMENT")
        values[key] = value
    rendered = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
    validate_set(rendered)
    return rendered


class BaselineBoundary:
    def __init__(self, service: Service) -> None:
        self.service = service

    def validate(self, definition: ExperimentDefinition) -> None:
        required = {o.metric for o in definition.objectives} | {
            c.metric for c in definition.constraints
        }
        if required - METRICS.keys():
            raise ValueError("UNSUPPORTED_REGISTERED_METRIC_REQUIRES_QUALIFIED_EXTRACTOR")
        # Do not pretend that prose defines executable cost/risk-normalization mathematics.
        if definition.evidence_classification != "EXPLORATORY_GROSS":
            raise ValueError("COST_MODELED_METRICS_REQUIRE_QUALIFIED_EXTRACTOR")

    def recover(self, run: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        with self.service.engine.connect() as conn:
            try:
                baseline = store.get(conn, UUID(run["id"]))
            except ValueError:
                return "INTERRUPTED_NOT_RETRIED", None
            if baseline.status in ACTIVE:
                raise RuntimeError("ACTIVE_EXECUTION_REQUIRES_OWNERSHIP_RECONCILIATION")
            if baseline.status == State.READY:
                return "INTERRUPTED_NOT_RETRIED", None
            if baseline.status != State.COMPLETE:
                return baseline.status.value, None
            result = store.result(conn, UUID(run["id"]))
        if (
            result is None
            or baseline.evidence_identity is None
            or result.baseline_run_id != UUID(run["id"])
            or result.project_id != baseline.config.project_id
            or result.candidate_id != baseline.candidate_id
            or result.result_identity != baseline.result_identity
        ):
            return "RESULT_VALIDATION_FAILED", None
        metrics = {
            key: None if result.metrics.get(source) is None else str(result.metrics[source])
            for key, source in METRICS.items()
        }
        if metrics["TRADE_COUNT"] == "0":
            metrics["PROFIT_FACTOR"] = None
        return "COMPLETE", {
            "metrics": metrics,
            "baseline_run_id": run["id"],
            "evidence_identity": baseline.evidence_identity,
            "result_identity": result.result_identity,
        }

    def execute(
        self,
        definition: ExperimentDefinition,
        candidate: dict[str, Any],
        run: dict[str, Any],
        deadline: datetime,
        cancelled: Event,
    ) -> tuple[str, dict[str, Any] | None]:
        self.validate(definition)
        if run["purpose"] not in {"DEVELOPMENT", "VALIDATION"}:
            raise ValueError("LOCKED_OOS_UNAVAILABLE")
        from trading_ecosystem.experiments.reference_contract import ReferenceDefinition

        if isinstance(definition, ReferenceDefinition):
            from trading_ecosystem.experiments import authorization

            with self.service.engine.connect() as conn:
                authorization.require(
                    conn,
                    UUID(run["campaign_id"]),
                    self.service.artifacts,
                    self.service.root,
                    run["purpose"],
                )
        split = definition.split_plan.splits[0 if run["purpose"] == "DEVELOPMENT" else 1]
        if (run["start"], run["end"], run["split_identity"]) != (
            str(split.start),
            str(split.end),
            split.identity,
        ):
            raise ValueError("SPLIT_IDENTITY_MISMATCH")
        remaining = int((deadline - datetime.now(UTC)).total_seconds())
        if cancelled.is_set():
            return "CANCELLED", None
        if remaining < 30:
            return "TIME_BUDGET_INSUFFICIENT", None
        key = UUID(run["id"])
        with self.service.engine.begin() as conn:
            base = readiness.get_configuration(conn, definition.baseline_configuration_id)
            if base["configuration_identity"] != definition.baseline_identity:
                raise ValueError("BASELINE_IDENTITY_MISMATCH")
            parameters = dict(base["specification"]["parameters"])
            parameters.update(
                from_date=run["start"],
                to_date=run["end"],
                timeout_seconds=min(parameters["timeout_seconds"], remaining),
                set_text=inputs(parameters.get("set_text"), candidate["assignments"]),
                input_provenance="USER_CONFIRMED_VALUES",
                input_reference=f"Frozen experiment {definition.identity}; {candidate['identity']}",
            )
            spec = readiness.BaselineConfiguration(
                configuration_id=uuid5(NAMESPACE_URL, run["identity"]),
                project_id=definition.project_id,
                parameters=parameters,
                confirmed=True,
            )
            readiness.save_configuration(conn, self.service.artifacts, spec)
            store.create(conn, spec.execution(key))
        if cancelled.is_set() or datetime.now(UTC) >= deadline:
            return "CANCELLED", None
        self.service.start(key)
        while self.service.thread is not None and self.service.thread.is_alive():
            if cancelled.wait(0.05) or datetime.now(UTC) >= deadline:
                if self.service.active_id == key:
                    self.service.cancel_event.set()
            self.service.thread.join(timeout=0.05)
        return self.recover(run)
