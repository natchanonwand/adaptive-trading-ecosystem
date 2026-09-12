"""Immutable synthetic OHLC simulation contracts."""

from datetime import timedelta
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, model_validator

from trading_ecosystem.benchmarks.contracts import (
    BenchmarkDefinition,
    BenchmarkId,
    ImmutableContract,
    ResearchDecision,
)
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import Price, UtcTimestamp, finite_decimal

Number = Annotated[Decimal, BeforeValidator(finite_decimal)]
Nonnegative = Annotated[Decimal, BeforeValidator(finite_decimal), Field(ge=0)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Exploratory(ImmutableContract):
    research_classification: Literal["EXPLORATORY_RESEARCH_ONLY"] = "EXPLORATORY_RESEARCH_ONLY"
    qualification_eligible: Literal[False] = False
    price_basis: Literal["MT5_CHART_BAR_BASIS_UNVERIFIED"] = "MT5_CHART_BAR_BASIS_UNVERIFIED"
    availability_basis: Literal["MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH"] = (
        "MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH"
    )


class SimulationBar(Exploratory):
    open_time: UtcTimestamp
    close_time: UtcTimestamp
    open: Price
    high: Price
    low: Price
    close: Price

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.close_time != self.open_time + timedelta(hours=1):
            raise ValueError("H1_DURATION_REQUIRED")
        if self.open_time.minute or self.open_time.second or self.open_time.microsecond:
            raise ValueError("H1_ALIGNMENT_REQUIRED")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("INVALID_OHLC")
        return self


class PriceIncrement(ImmutableContract):
    tick_size: Price
    provenance: Literal["EXPLICIT_SYNTHETIC_ASSUMPTION"] = "EXPLICIT_SYNTHETIC_ASSUMPTION"


class CostModel(ImmutableContract):
    # Required, including explicit zeros: no hidden broker assumptions.
    entry_spread_price: Nonnegative
    entry_slippage_price: Nonnegative
    exit_spread_price: Nonnegative
    exit_slippage_price: Nonnegative
    commission_cash: Nonnegative
    financing_cash: Number
    provenance: Literal["EXPLICIT_SYNTHETIC_ASSUMPTIONS"] = "EXPLICIT_SYNTHETIC_ASSUMPTIONS"


class EntryIntent(Exploratory):
    benchmark_id: BenchmarkId
    decision_time: UtcTimestamp
    available_at: UtcTimestamp
    eligibility: Literal[ResearchDecision.ENTRY_ELIGIBLE] = ResearchDecision.ENTRY_ELIGIBLE
    signal_stop_raw: Price

    @model_validator(mode="after")
    def known(self) -> Self:
        if self.available_at != self.decision_time:
            raise ValueError("ELIGIBILITY_MUST_BE_KNOWN_AT_SIGNAL_CLOSE")
        return self


class StrategyExitIntent(Exploratory):
    benchmark_id: BenchmarkId
    decision_time: UtcTimestamp
    available_at: UtcTimestamp
    eligibility: Literal[ResearchDecision.EXIT_ELIGIBLE] = ResearchDecision.EXIT_ELIGIBLE

    @model_validator(mode="after")
    def known(self) -> Self:
        if self.available_at != self.decision_time:
            raise ValueError("EXIT_ELIGIBILITY_MUST_BE_KNOWN_AT_CLOSE")
        if self.benchmark_id == BenchmarkId.B01:
            raise ValueError("B01_HAS_NO_STRATEGY_EXIT")
        return self


class ModeledEntryFill(Exploratory):
    decision_time: UtcTimestamp
    price_reference_time: UtcTimestamp
    modeled_execution_time: UtcTimestamp
    price_source: Literal["NEXT_OBSERVED_BAR_OPEN"] = "NEXT_OBSERVED_BAR_OPEN"
    reference_open: Price
    spread_component: Nonnegative
    adverse_slippage_component: Nonnegative
    entry_fill: Price

    @model_validator(mode="after")
    def chronology(self) -> Self:
        if self.price_reference_time < self.decision_time or self.modeled_execution_time != (
            max(self.decision_time, self.price_reference_time) + timedelta(microseconds=1)
        ):
            raise ValueError("INVALID_MODELED_OPEN_TIME")
        with arithmetic_context():
            if (
                self.entry_fill
                != self.reference_open + self.spread_component + self.adverse_slippage_component
            ):
                raise ValueError("ENTRY_COMPONENT_MISMATCH")
        return self


class ProtectiveStop(ImmutableContract):
    signal_stop_raw: Price
    fixed_stop: Nonnegative
    rounding: Literal["DOWN_TO_SUPPLIED_TICK"] = "DOWN_TO_SUPPLIED_TICK"
    fixed: Literal[True] = True

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.fixed_stop > self.signal_stop_raw:
            raise ValueError("STOP_MUST_ROUND_DOWN")
        return self


class TakeProfitTarget(ImmutableContract):
    target_raw: Price
    target: Price
    r_multiple: Literal[2] = 2
    basis: Literal["MODELED_ENTRY_FILL_MINUS_FIXED_STOP"] = "MODELED_ENTRY_FILL_MINUS_FIXED_STOP"
    rounding: Literal["UP_TO_SUPPLIED_TICK"] = "UP_TO_SUPPLIED_TICK"

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.target < self.target_raw:
            raise ValueError("TARGET_MUST_ROUND_UP")
        return self


class ExitReason(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TREND_EXIT = "TREND_EXIT"
    CHANNEL_EXIT = "CHANNEL_EXIT"
    EVALUATION_BOUNDARY = "EVALUATION_BOUNDARY"


class ExitFill(Exploratory):
    reason: ExitReason
    price_reference_time: UtcTimestamp
    modeled_execution_time: UtcTimestamp
    decision_time: UtcTimestamp | None = None
    price_source: Literal["NEXT_OBSERVED_BAR_OPEN", "BAR_OPEN", "INTRABAR_LEVEL", "BOUNDARY_CLOSE"]
    exit_price: Nonnegative
    # Recorded independently; not deducted from price-path exit or gross price R.
    spread_component: Nonnegative
    adverse_slippage_component: Nonnegative
    gap_exit: bool = Field(strict=True)
    intrabar_ambiguous: bool = Field(strict=True)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.modeled_execution_time < self.price_reference_time:
            raise ValueError("EXECUTION_BEFORE_REFERENCE")
        if self.intrabar_ambiguous and (self.gap_exit or self.reason != ExitReason.STOP_LOSS):
            raise ValueError("AMBIGUITY_REQUIRES_INTRABAR_STOP_FIRST")
        if self.price_source == "NEXT_OBSERVED_BAR_OPEN":
            if self.decision_time is None or self.price_reference_time < self.decision_time:
                raise ValueError("STRATEGY_EXIT_REQUIRES_PRIOR_DECISION")
            if self.modeled_execution_time != self.price_reference_time + timedelta(microseconds=1):
                raise ValueError("INVALID_STRATEGY_EXECUTION_TIME")
        return self


class SimulatedPosition(Exploratory):
    benchmark_id: BenchmarkId
    direction: Literal["LONG_ONLY"] = "LONG_ONLY"
    synthetic_unit_quantity: Literal[1] = 1
    entry: ModeledEntryFill
    stop: ProtectiveStop
    target: TakeProfitTarget | None
    initial_price_risk: Price

    @model_validator(mode="after")
    def valid(self) -> Self:
        with arithmetic_context():
            if self.initial_price_risk != self.entry.entry_fill - self.stop.fixed_stop:
                raise ValueError("INVALID_INITIAL_PRICE_RISK")
            if (self.target is not None) != (self.benchmark_id == BenchmarkId.B01):
                raise ValueError("BENCHMARK_TARGET_POLICY_MISMATCH")
            if (
                self.target is not None
                and self.target.target_raw != self.entry.entry_fill + 2 * self.initial_price_risk
            ):
                raise ValueError("TARGET_MUST_USE_ACTUAL_MODELED_ENTRY")
        return self


class CompletedEpisode(Exploratory):
    position: SimulatedPosition
    exit: ExitFill
    gross_price_R: Number
    costs: CostModel
    monetary_net_R: Literal[None] = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.exit.modeled_execution_time < self.position.entry.modeled_execution_time:
            raise ValueError("EXIT_BEFORE_ENTRY")
        with arithmetic_context():
            expected = (
                self.exit.exit_price - self.position.entry.entry_fill
            ) / self.position.initial_price_risk
            if self.gross_price_R != expected:
                raise ValueError("GROSS_PRICE_R_MISMATCH")
        return self


class EventKind(IntEnum):
    SIGNAL_DECISION = 10
    ENTRY_INTENT = 20
    ENTRY_FILL = 30
    PROTECTIVE_STOP_ACTIVE = 40
    TAKE_PROFIT_ACTIVE = 50
    STOP_EXIT = 60
    TARGET_EXIT = 70
    STRATEGY_EXIT_DECISION = 80
    STRATEGY_EXIT_FILL = 90
    EVALUATION_BOUNDARY = 100
    BOUNDARY_STATUS = 110


class SimulationEvent(Exploratory):
    sequence: Annotated[int, Field(strict=True, ge=0)]
    kind: EventKind
    time: UtcTimestamp
    bar_index: Annotated[int, Field(strict=True, ge=0)]
    detail: str
    entry: ModeledEntryFill | None = None
    exit: ExitFill | None = None


class ResultStatus(StrEnum):
    NO_FILL_END_OF_DATA = "NO_FILL_END_OF_DATA"
    INVALID_INITIAL_PRICE_RISK = "INVALID_INITIAL_PRICE_RISK"
    OPEN_AT_EVALUATION_BOUNDARY = "OPEN_AT_EVALUATION_BOUNDARY"
    COMPLETED = "COMPLETED"


class SimulationSpec(Exploratory):
    schema_version: Literal["simulation-spec-v0.1.0"] = "simulation-spec-v0.1.0"
    execution_model_version: Literal["exploratory-ohlc-v0.1.0"] = "exploratory-ohlc-v0.1.0"
    benchmark: BenchmarkDefinition
    bars: tuple[SimulationBar, ...]
    entry_intent: EntryIntent
    strategy_exits: tuple[StrategyExitIntent, ...] = ()
    increment: PriceIncrement
    costs: CostModel
    flatten_at_boundary: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.benchmark.benchmark_id != self.entry_intent.benchmark_id:
            raise ValueError("BENCHMARK_MISMATCH")
        for previous, current in zip(self.bars, self.bars[1:], strict=False):
            if current.open_time < previous.close_time:
                raise ValueError("BARS_MUST_BE_ORDERED_NONOVERLAPPING")
        closes = {bar.close_time for bar in self.bars}
        if self.entry_intent.decision_time not in closes:
            raise ValueError("ENTRY_MUST_MATCH_COMPLETED_SIGNAL_BAR")
        previous_time = self.entry_intent.decision_time
        for intent in self.strategy_exits:
            if intent.benchmark_id != self.benchmark.benchmark_id:
                raise ValueError("EXIT_BENCHMARK_MISMATCH")
            if intent.decision_time not in closes or intent.decision_time <= previous_time:
                raise ValueError("EXIT_INTENTS_MUST_BE_UNIQUE_ORDERED_COMPLETED_BARS_AFTER_ENTRY")
            previous_time = intent.decision_time
        return self


class SimulationResult(Exploratory):
    schema_version: Literal["simulation-result-v0.1.0"] = "simulation-result-v0.1.0"
    specification_sha256: Digest
    status: ResultStatus
    events: tuple[SimulationEvent, ...]
    position: SimulatedPosition | None
    episode: CompletedEpisode | None
    pending_strategy_exit: StrategyExitIntent | None = None
