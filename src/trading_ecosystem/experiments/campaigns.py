"""Versioned runtime planning; frozen Phase 5C.0 contracts remain unchanged."""

from decimal import Decimal
from typing import Any

from trading_ecosystem.experiments.contracts import ExperimentDefinition, digest
from trading_ecosystem.experiments.governance import candidate_at, evaluate_constraints

PROTOCOL = "CONTROLLED_DEVELOPMENT_VALIDATION_V1"


def generate(definition: ExperimentDefinition) -> list[dict[str, Any]]:
    """Reuse registered ordinal sampling; duplicates consume slots, never replenish them."""
    definition = ExperimentDefinition.model_validate_json(definition.model_dump_json())
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ordinal in range(definition.budget.maximum_configurations):
        try:
            planned = candidate_at(definition, ordinal)
        except ValueError as exc:
            if str(exc) == "GRID_DOMAIN_EXHAUSTED":
                break
            raise
        assignments = dict(planned.parameter_values)
        for parameter in definition.parameter_space.parameters:
            if parameter.kind in {"INTEGER", "DECIMAL"}:
                assignments[parameter.native_key] = format(
                    Decimal(assignments[parameter.native_key]).normalize(), "f"
                )
        content = {
            "definition": definition.identity,
            "baseline": definition.baseline_identity,
            "assignments": assignments,
            "model": definition.tester_model,
            "protocol": PROTOCOL,
        }
        identity = digest(content)
        if identity not in seen:
            candidates.append({"identity": identity, "ordinal": ordinal, **content})
            seen.add(identity)
    return candidates


def bindings(definition: ExperimentDefinition) -> dict[str, str]:
    return {
        "definition": definition.identity,
        "parameter_space": definition.parameter_space.identity,
        "budget": definition.budget.identity,
        "split_plan": definition.split_plan.identity,
        "objective": digest([o.model_dump(mode="json") for o in definition.objectives]),
        "constraint": digest([c.model_dump(mode="json") for c in definition.constraints]),
        "candidate": str(definition.candidate_id),
        "baseline": definition.baseline_identity,
    }


def select_development(
    definition: ExperimentDefinition, runs: list[dict[str, Any]]
) -> tuple[list[str], dict[str, str]]:
    """Freeze all tied lexicographic winners or the Pareto front, in candidate order."""
    eligible: list[tuple[str, tuple[Decimal, ...]]] = []
    decisions: dict[str, str] = {}
    for run in runs:
        if run["purpose"] != "DEVELOPMENT":
            raise ValueError("NON_DEVELOPMENT_SELECTION_INPUT")
        key = str(run["configuration_identity"])
        if run["status"] != "COMPLETE":
            decisions[key] = "EXECUTION_FAILURE"
            continue
        metrics = run["observation"]["metrics"]
        state, _ = evaluate_constraints(definition, tuple(metrics.items()))
        if state != "ELIGIBLE":
            decisions[key] = "CONSTRAINT_" + state
            continue
        if any(metrics.get(o.metric) is None for o in definition.objectives):
            decisions[key] = "OBJECTIVE_UNDEFINED"
            continue
        scores = tuple(
            Decimal(metrics[o.metric]) * (1 if o.direction == "MAXIMIZE" else -1)
            for o in definition.objectives
        )
        if any(not value.is_finite() for value in scores):
            raise ValueError("NONFINITE_OBJECTIVE")
        eligible.append((key, scores))
        decisions[key] = "ELIGIBLE_NOT_SELECTED"
    if definition.evaluation_method == "DECLARED_LEXICOGRAPHIC":
        best = max((scores for _, scores in eligible), default=())
        selected = [key for key, scores in eligible if scores == best]
    else:
        selected = [
            key
            for key, scores in eligible
            if not any(
                all(b >= a for a, b in zip(scores, other, strict=True))
                and any(b > a for a, b in zip(scores, other, strict=True))
                for _, other in eligible
            )
        ]
    for key in selected:
        decisions[key] = "DEVELOPMENT_SELECTED"
    return selected, decisions


def observation(value: dict[str, Any]) -> dict[str, Any]:
    """Validate linked normalized evidence, never synthesize execution metrics."""
    if set(value) != {"metrics", "baseline_run_id", "evidence_identity", "result_identity"}:
        raise ValueError("INVALID_OBSERVATION")
    from uuid import UUID

    UUID(value["baseline_run_id"])
    for key in ("evidence_identity", "result_identity"):
        identity = value[key]
        if (
            not isinstance(identity, str)
            or len(identity) != 64
            or any(c not in "0123456789abcdef" for c in identity)
        ):
            raise ValueError("INVALID_EVIDENCE_LINK")
    metrics = value["metrics"]
    if not isinstance(metrics, dict):
        raise ValueError("INVALID_METRICS")
    for raw in metrics.values():
        if raw is not None and (not isinstance(raw, str) or not Decimal(raw).is_finite()):
            raise ValueError("INVALID_METRIC")
    count = metrics.get("TRADE_COUNT")
    if count is None or Decimal(count) < 0 or Decimal(count) % 1:
        raise ValueError("INVALID_TRADE_COUNT")
    if Decimal(count) == 0 and any(
        metrics.get(key) is not None for key in ("PROFIT_FACTOR", "EXPECTANCY")
    ):
        raise ValueError("ZERO_TRADE_RATIO_MUST_BE_NULL")
    return value
