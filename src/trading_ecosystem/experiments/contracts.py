"""Immutable experiment definitions; no outcomes, native execution or adaptive search."""

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, StrictInt, model_validator

from trading_ecosystem.domain.primitives import FrozenModel


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class Content(FrozenModel):
    @property
    def identity(self) -> str:
        return digest(self.model_dump(mode="json"))


class Condition(Content):
    native_key: str = Field(min_length=1, max_length=100)
    equals: str = Field(min_length=1, max_length=100)


class Parameter(Content):
    parameter_name: str = Field(min_length=1, max_length=100)
    native_key: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")
    kind: Literal["INTEGER", "DECIMAL", "BOOLEAN", "CATEGORY"]
    baseline: str = Field(min_length=1, max_length=100)
    minimum: str | None = None
    maximum: str | None = None
    step: str | None = None
    choices: tuple[str, ...] = Field(default=(), max_length=1000)
    transformation: Literal["IDENTITY"] = "IDENTITY"
    reason: str = Field(min_length=1, max_length=1000)
    provenance: Literal[
        "VENDOR_DOCUMENTATION",
        "USER_DECLARATION",
        "STRATEGY_SPECIFICATION",
        "REGISTERED_HYPOTHESIS",
    ]
    source_reference: str = Field(min_length=1, max_length=1000)
    conditional: Condition | None = None
    categorical: bool
    ordered: bool

    @model_validator(mode="after")
    def valid(self) -> Self:
        if any(
            v.strip().upper() in {"", "UNKNOWN", "UNAVAILABLE"}
            for v in (self.reason, self.source_reference, self.parameter_name)
        ):
            raise ValueError("EXPLICIT_PARAMETER_PROVENANCE_REQUIRED")
        if self.categorical != (self.kind in {"BOOLEAN", "CATEGORY"}):
            raise ValueError("PARAMETER_CATEGORY_MISMATCH")
        if len(set(self.choices)) != len(self.choices) or any(not v for v in self.choices):
            raise ValueError("INVALID_DISCRETE_CHOICES")
        bounds = (self.minimum, self.maximum, self.step)
        if self.choices:
            if any(v is not None for v in bounds) or self.baseline not in self.choices:
                raise ValueError("DISCRETE_BASELINE_OR_RANGE_INVALID")
        elif self.kind not in {"INTEGER", "DECIMAL"} or any(v is None for v in bounds):
            raise ValueError("EXPLICIT_PARAMETER_DOMAIN_REQUIRED")
        if self.kind == "BOOLEAN" and set(self.choices) != {"true", "false"}:
            raise ValueError("BOOLEAN_CHOICES_REQUIRED")
        if self.kind in {"INTEGER", "DECIMAL"}:
            if not self.ordered:
                raise ValueError("NUMERIC_PARAMETER_MUST_BE_ORDERED")
            values = (self.baseline, *self.choices, *(v for v in bounds if v is not None))
            for value in values:
                try:
                    n = Decimal(value)
                except InvalidOperation:
                    raise ValueError("INVALID_NUMERIC_PARAMETER") from None
                if (
                    not n.is_finite()
                    or len(value) > 50
                    or abs(int(n.as_tuple().exponent)) > 12
                    or len(n.as_tuple().digits) > 18
                    or (self.kind == "INTEGER" and n != n.to_integral_value())
                ):
                    raise ValueError("INVALID_NUMERIC_PARAMETER")
            if not self.choices:
                lo, hi, step = (Decimal(str(v)) for v in bounds)
                if (
                    not lo <= Decimal(self.baseline) <= hi
                    or step <= 0
                    or (hi - lo) % step
                    or (Decimal(self.baseline) - lo) % step
                ):
                    raise ValueError("INVALID_PARAMETER_RANGE_OR_STEP")
                if (hi - lo) / step > 999:
                    raise ValueError("PARAMETER_DOMAIN_LIMIT")
        return self

    def domain(self) -> tuple[str, ...]:
        if self.choices:
            return self.choices
        lo, hi, step = (
            Decimal(str(self.minimum)),
            Decimal(str(self.maximum)),
            Decimal(str(self.step)),
        )
        return tuple(format(lo + i * step, "f") for i in range(int((hi - lo) / step) + 1))


class ParameterSpace(Content):
    parameters: tuple[Parameter, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def valid(self) -> Self:
        seen: dict[str, Parameter] = {}
        names: set[str] = set()
        for p in self.parameters:
            if p.native_key in seen or p.parameter_name in names:
                raise ValueError("DUPLICATE_PARAMETER")
            if p.conditional and (
                p.conditional.native_key not in seen
                or p.conditional.equals not in seen[p.conditional.native_key].domain()
            ):
                raise ValueError("CONDITION_MUST_REFERENCE_EARLIER_DECLARED_DOMAIN")
            seen[p.native_key] = p
            names.add(p.parameter_name)
        return self


class Budget(Content):
    maximum_configurations: StrictInt = Field(ge=1, le=10000)
    maximum_native_executions: StrictInt = Field(ge=1, le=30000)
    method: Literal["GRID", "RANDOM_SEEDED"]
    random_seed: StrictInt | None = Field(default=None, ge=0, le=2**32 - 1)
    maximum_wall_seconds: StrictInt = Field(ge=1, le=604800)
    maximum_workers: Literal[1] = 1
    early_rejection: Literal["NONE", "PRE_REGISTERED_HARD_CONSTRAINTS"] = "NONE"

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (self.method == "RANDOM_SEEDED") != (self.random_seed is not None):
            raise ValueError("EXPLICIT_SEED_FOR_RANDOM_ONLY")
        if self.maximum_native_executions < self.maximum_configurations:
            raise ValueError("EXECUTION_BUDGET_TOO_SMALL")
        return self


class Split(Content):
    start: date
    end: date
    purpose: Literal["DEVELOPMENT", "VALIDATION", "LOCKED_OOS"]
    locked: Literal[True] = True

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.start >= self.end:
            raise ValueError("INVALID_HALF_OPEN_INTERVAL")
        return self


class DataSplitPlan(Content):
    splits: tuple[Split, Split, Split]

    @model_validator(mode="after")
    def valid(self) -> Self:
        if tuple(s.purpose for s in self.splits) != ("DEVELOPMENT", "VALIDATION", "LOCKED_OOS"):
            raise ValueError("CHRONOLOGICAL_PURPOSE_ORDER_REQUIRED")
        if any(a.end > b.start for a, b in zip(self.splits, self.splits[1:], strict=False)):
            raise ValueError("OVERLAPPING_SPLITS")
        return self


Metric = Literal[
    "RETURN_R",
    "NET_PROFIT",
    "PROFIT_FACTOR",
    "EXPECTANCY",
    "DRAWDOWN_ADJUSTED_RETURN",
    "STABILITY",
    "MAX_DRAWDOWN_PCT",
    "TRADE_COUNT",
    "ACTIVITY",
    "CONCENTRATION",
]


class Objective(Content):
    metric: Metric
    direction: Literal["MAXIMIZE", "MINIMIZE"]
    definition: str = Field(min_length=1, max_length=1000)
    null_policy: Literal["INELIGIBLE"] = "INELIGIBLE"


class Constraint(Content):
    metric: Metric
    comparator: Literal["AT_LEAST", "AT_MOST"]
    threshold: str = Field(min_length=1, max_length=50)
    rationale: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def valid(self) -> Self:
        try:
            value = Decimal(self.threshold)
        except InvalidOperation:
            raise ValueError("INVALID_CONSTRAINT_THRESHOLD") from None
        if not value.is_finite():
            raise ValueError("INVALID_CONSTRAINT_THRESHOLD")
        return self


class ExperimentDefinition(Content):
    schema_version: Literal["EXPERIMENT_DEFINITION_V1"] = "EXPERIMENT_DEFINITION_V1"
    project_id: UUID
    candidate_id: UUID
    baseline_configuration_id: UUID
    baseline_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    hypothesis: str = Field(min_length=1, max_length=2000)
    parameter_space: ParameterSpace
    budget: Budget
    split_plan: DataSplitPlan
    objectives: tuple[Objective, ...] = Field(min_length=1, max_length=10)
    evaluation_method: Literal["PARETO_REVIEW", "DECLARED_LEXICOGRAPHIC"]
    constraints: tuple[Constraint, ...] = Field(min_length=1, max_length=20)
    tester_model: Literal["EVERY_TICK_BASED_ON_REAL_TICKS"] = "EVERY_TICK_BASED_ON_REAL_TICKS"
    cost_assumptions: str = Field(min_length=1, max_length=2000)
    broker_environment: Literal["DEMO_RESEARCH_TESTER"] = "DEMO_RESEARCH_TESTER"
    broker: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=100)
    timeframe: str = Field(pattern=r"^(M[1-9][0-9]*|H[1-9][0-9]*|D1|W1|MN1)$")
    data_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_classification: Literal["EXPLORATORY_GROSS", "EXPLORATORY_COST_MODELED"]
    qualification_eligible: Literal[False] = False

    @model_validator(mode="after")
    def valid(self) -> Self:
        metrics = tuple(o.metric for o in self.objectives)
        if len(set(metrics)) != len(metrics) or set(metrics) == {"NET_PROFIT"}:
            raise ValueError("EXPLICIT_NON_PROFIT_ONLY_OBJECTIVE_REQUIRED")
        return self


class ExperimentCampaign(Content):
    definition_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    protocol: Literal["PRE_REGISTERED_NO_EXECUTION_V1"] = "PRE_REGISTERED_NO_EXECUTION_V1"
    execution_enabled: Literal[False] = False


class ExperimentRun(Content):
    campaign_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    definition_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    split_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    ordinal: StrictInt = Field(ge=0)
    parameter_values: tuple[tuple[str, str], ...]
    state: Literal["PLANNED_CONTRACT_ONLY"] = "PLANNED_CONTRACT_ONLY"


class SelectionDecision(Content):
    """Future interface only. No champion election or OOS capability is implemented."""

    campaign_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_configuration_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    development_evidence_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_evidence_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    rationale: str = Field(min_length=1, max_length=2000)
    locked: Literal[True] = True
