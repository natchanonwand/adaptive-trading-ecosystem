"""Pure planning and governance interfaces; never enumerate a real campaign or execute it."""

from datetime import date
from decimal import Decimal
from typing import Literal

from trading_ecosystem.experiments.contracts import (
    ExperimentCampaign,
    ExperimentDefinition,
    ExperimentRun,
    digest,
)


def candidate_at(definition: ExperimentDefinition, ordinal: int) -> ExperimentRun:
    """Deterministic contract lookup, used only with synthetic fixtures in Phase 5C.0.

    Mixed-radix grid ordering or SHA256 counter-based seeded sampling. No outcome,
    feature, validation or OOS values are accepted. Random sampling is with replacement;
    every ordinal counts against the pre-registered budget, including duplicates.
    """
    if isinstance(ordinal, bool) or not 0 <= ordinal < definition.budget.maximum_configurations:
        raise ValueError("CONFIGURATION_BUDGET_EXCEEDED")
    campaign = ExperimentCampaign(definition_identity=definition.identity)
    offset = ordinal
    chosen: dict[str, str] = {}
    for index, parameter in enumerate(definition.parameter_space.parameters):
        domain = parameter.domain()
        if definition.budget.method == "GRID":
            choice = offset % len(domain)
            offset //= len(domain)
        else:
            choice = int(
                digest([definition.identity, definition.budget.random_seed, ordinal, index]), 16
            ) % len(domain)
        # Inactive conditional inputs retain the declared baseline, never invented values.
        active = (
            parameter.conditional is None
            or chosen[parameter.conditional.native_key] == parameter.conditional.equals
        )
        chosen[parameter.native_key] = domain[choice] if active else parameter.baseline
    if definition.budget.method == "GRID" and offset:
        raise ValueError("GRID_DOMAIN_EXHAUSTED")
    return ExperimentRun(
        campaign_identity=campaign.identity,
        definition_identity=definition.identity,
        split_identity=definition.split_plan.splits[0].identity,
        ordinal=ordinal,
        parameter_values=tuple(chosen.items()),
    )


def feature_cutoff(definition: ExperimentDefinition, available_through: date) -> None:
    split = definition.split_plan.splits[0]
    if not split.start <= available_through < split.end:
        raise ValueError("FUTURE_OR_NON_DEVELOPMENT_DATA_FORBIDDEN")


def evaluate_constraints(
    definition: ExperimentDefinition,
    metrics: tuple[tuple[str, str | None], ...],
) -> tuple[Literal["ELIGIBLE", "REJECTED", "INSUFFICIENT_EVIDENCE"], tuple[str, ...]]:
    """A valid zero-trade observation may fail eligibility, never execution/parser status."""
    if len(dict(metrics)) != len(metrics):
        raise ValueError("DUPLICATE_OBSERVATION_METRIC")
    values = dict(metrics)
    failures: list[str] = []
    unknown: list[str] = []
    for rule in definition.constraints:
        raw = values.get(rule.metric)
        if raw is None:
            unknown.append(rule.metric)
            continue
        value = Decimal(raw)
        if not value.is_finite():
            raise ValueError("INVALID_OBSERVATION")
        passes = (
            value >= Decimal(rule.threshold)
            if rule.comparator == "AT_LEAST"
            else value <= Decimal(rule.threshold)
        )
        if not passes:
            failures.append(rule.metric)
    if failures:
        return "REJECTED", tuple(failures)
    if unknown:
        return "INSUFFICIENT_EVIDENCE", tuple(unknown)
    return "ELIGIBLE", ()
