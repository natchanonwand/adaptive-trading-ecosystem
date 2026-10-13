"""Explicit reference protocol extension; legacy experiment semantics remain V1."""

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from trading_ecosystem.experiments.contracts import ExperimentDefinition


class ReferenceDefinition(ExperimentDefinition):
    reference_protocol: Literal["REFERENCE_EMA_PIPELINE_V1"]
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical_ex5_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    build_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    development_limit: Literal[9] = 9
    validation_limit: Literal[2] = 2
    selection_limit: Literal[2] = 2
    source_provenance: Literal["PROJECT_SOURCE"] = "PROJECT_SOURCE"
    range_provenance: Literal["OPERATOR_DEFINED_RESEARCH_HYPOTHESIS"] = (
        "OPERATOR_DEFINED_RESEARCH_HYPOTHESIS"
    )

    @model_validator(mode="after")
    def valid(self) -> Self:
        # Overrides only the V1 objective validator, never changes V1 acceptance.
        if (
            [(o.metric, o.direction) for o in self.objectives] != [("NET_PROFIT", "MAXIMIZE")]
            or [(c.metric, c.comparator, c.threshold) for c in self.constraints]
            != [("TRADE_COUNT", "AT_LEAST", "10")]
            or self.evaluation_method != "DECLARED_LEXICOGRAPHIC"
            or self.evidence_classification != "EXPLORATORY_GROSS"
        ):
            raise ValueError("REFERENCE_OBJECTIVE_ACTIVITY_POLICY_REQUIRED")
        if (
            self.budget.method != "GRID"
            or self.budget.maximum_configurations != 9
            or self.budget.maximum_native_executions != 11
            or self.budget.maximum_workers != 1
        ):
            raise ValueError("REFERENCE_BUDGET_MUST_BE_9_PLUS_2")
        expected = [
            ("InpFastEmaPeriod", "20", ("10", "20", "30")),
            ("InpSlowEmaPeriod", "100", ("60", "100", "140")),
        ]
        if len(self.parameter_space.parameters) != 2:
            raise ValueError("REFERENCE_EXACT_PARAMETER_SPACE_REQUIRED")
        for p, (key, baseline, choices) in zip(
            self.parameter_space.parameters, expected, strict=True
        ):
            if (
                (p.native_key, p.baseline, p.choices) != (key, baseline, choices)
                or p.kind != "INTEGER"
                or p.conditional is not None
                or p.provenance != "STRATEGY_SPECIFICATION"
                or self.source_sha256 not in p.source_reference
                or "PROJECT_SOURCE" not in p.source_reference
            ):
                raise ValueError("REFERENCE_PARAMETER_PROVENANCE_MISMATCH")
        dates = [(str(s.start), str(s.end)) for s in self.split_plan.splits]
        if dates != [
            ("2026-01-01", "2026-04-01"),
            ("2026-04-01", "2026-05-16"),
            ("2026-05-16", "2026-07-01"),
        ] or (self.symbol, self.timeframe) != ("XAUUSDm", "M5"):
            raise ValueError("REFERENCE_SPLITS_OR_SYMBOL_CHANGED")
        return self


def parse_definition(value: Any) -> ExperimentDefinition:
    if isinstance(value, ExperimentDefinition):
        value = value.model_dump(mode="json")
    if isinstance(value, dict) and "reference_protocol" in value:
        return ReferenceDefinition.model_validate(value)
    return ExperimentDefinition.model_validate(value)
