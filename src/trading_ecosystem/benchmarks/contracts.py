"""Frozen preregistration and supplied-research-value contracts."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from trading_ecosystem.domain.primitives import FrozenModel, Price, UtcTimestamp


class ImmutableContract(FrozenModel):
    model_config = ConfigDict(revalidate_instances="always")

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        return type(self).model_validate({**self.model_dump(), **(update or {})})

    # Pydantic mypy synthesizes this signature; runtime rejects unchecked creation.
    @classmethod
    def model_construct(  # type: ignore[override]
        cls, _fields_set: set[str] | None = None, **values: Any
    ) -> Self:
        raise TypeError("UNCHECKED_BENCHMARK_CONSTRUCTION_FORBIDDEN")


class BenchmarkId(StrEnum):
    B01 = "B01_LEGACY_HYBRID_V0"
    B02 = "B02_EMA_TREND_50_200"
    B03 = "B03_CHANNEL_20_10"
    B04 = "B04_CHANNEL_55_20"


BENCHMARK_ORDER = (BenchmarkId.B01, BenchmarkId.B02, BenchmarkId.B03, BenchmarkId.B04)


class BenchmarkFamily(StrEnum):
    LEGACY_HYBRID = "LEGACY_HYBRID"
    MOVING_AVERAGE_TREND = "MOVING_AVERAGE_TREND"
    CHANNEL_TREND = "CHANNEL_TREND"


class Direction(StrEnum):
    LONG_ONLY = "LONG_ONLY"


class TimeBasis(StrEnum):
    H1_OBSERVED_BAR = "H1_OBSERVED_BAR"


class OriginCategory(StrEnum):
    PROJECT_LEGACY_HYPOTHESIS = "PROJECT_LEGACY_HYPOTHESIS"
    MOVING_AVERAGE_TREND_BENCHMARK = "MOVING_AVERAGE_TREND_BENCHMARK"
    CHANNEL_TREND_BENCHMARK = "CHANNEL_TREND_BENCHMARK"


class EntryKind(StrEnum):
    HYBRID_TREND_AND_BREAKOUT = "HYBRID_TREND_AND_BREAKOUT"
    BULLISH_EMA_CROSS = "BULLISH_EMA_CROSS"
    CHANNEL_BREAKOUT = "CHANNEL_BREAKOUT"


class ExitKind(StrEnum):
    NONE = "NONE"
    BEARISH_OR_EQUAL_EMA_CROSS = "BEARISH_OR_EQUAL_EMA_CROSS"
    CHANNEL_EXIT = "CHANNEL_EXIT"


class NormalExit(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    PROTECTIVE_STOP = "PROTECTIVE_STOP"
    TREND_EXIT = "TREND_EXIT"
    CHANNEL_EXIT = "CHANNEL_EXIT"


class TakeProfitKind(StrEnum):
    NONE = "NONE"
    FIXED_PRICE_R_MULTIPLE = "FIXED_PRICE_R_MULTIPLE"


Period = Annotated[int, Field(strict=True, ge=1)]
ObservationCount = Annotated[int, Field(strict=True, ge=0)]


class EntryRule(ImmutableContract):
    kind: EntryKind
    fast_ema_period: Period | None = None
    slow_ema_period: Period | None = None
    previous_high_period: Period | None = None
    comparison: Literal["STRICT"] = "STRICT"
    current_high_excluded: Literal[True] = True

    @model_validator(mode="after")
    def shape(self) -> Self:
        fast, slow, channel = self.fast_ema_period, self.slow_ema_period, self.previous_high_period
        if self.kind == EntryKind.CHANNEL_BREAKOUT:
            if fast is not None or slow is not None or channel is None:
                raise ValueError("INVALID_CHANNEL_ENTRY")
        elif fast is None or slow is None or fast >= slow:
            raise ValueError("INVALID_EMA_ENTRY")
        elif (channel is not None) != (self.kind == EntryKind.HYBRID_TREND_AND_BREAKOUT):
            raise ValueError("INVALID_ENTRY_COMPOSITION")
        return self


class ExitRule(ImmutableContract):
    kind: ExitKind
    previous_low_period: Period | None = None
    normal_exits: tuple[NormalExit, ...]
    current_low_excluded: Literal[True] = True

    @model_validator(mode="after")
    def shape(self) -> Self:
        if (self.previous_low_period is not None) != (self.kind == ExitKind.CHANNEL_EXIT):
            raise ValueError("INVALID_EXIT_COMPOSITION")
        if not self.normal_exits or len(set(self.normal_exits)) != len(self.normal_exits):
            raise ValueError("INVALID_NORMAL_EXITS")
        return self


class ProtectiveStopPolicy(ImmutableContract):
    atr_type: Literal["WILDER"] = "WILDER"
    atr_period: Literal[14] = 14
    atr_multiple: Literal[2] = 2
    reference: Literal["SIGNAL_CLOSE_MINUS_MULTIPLE_ATR"] = "SIGNAL_CLOSE_MINUS_MULTIPLE_ATR"
    fixed_after_entry: Literal[True] = True
    tick_rounding: Literal["DEFERRED_INSTRUMENT_POLICY"] = "DEFERRED_INSTRUMENT_POLICY"


class TakeProfitPolicy(ImmutableContract):
    kind: TakeProfitKind
    r_multiple: Literal[2] | None = None
    initial_price_risk_basis: Literal["ACTUAL_SIMULATED_ENTRY_FILL_MINUS_FIXED_STOP"] | None = None
    target_basis: (
        Literal["ACTUAL_SIMULATED_ENTRY_FILL_PLUS_R_MULTIPLE_OF_INITIAL_PRICE_RISK"] | None
    ) = None

    @model_validator(mode="after")
    def shape(self) -> Self:
        fields = (self.r_multiple, self.initial_price_risk_basis, self.target_basis)
        if self.kind == TakeProfitKind.NONE and any(value is not None for value in fields):
            raise ValueError("NONE_TP_REQUIRES_EMPTY_METADATA")
        if self.kind == TakeProfitKind.FIXED_PRICE_R_MULTIPLE and any(
            value is None for value in fields
        ):
            raise ValueError("ACTUAL_ENTRY_BASIS_REQUIRED")
        return self


class DecisionTiming(ImmutableContract):
    evaluation: Literal["COMPLETED_H1_BAR_ONLY"] = "COMPLETED_H1_BAR_ONLY"
    decision_time: Literal["BAR_CLOSE_TIME"] = "BAR_CLOSE_TIME"
    future_execution: Literal["STRICTLY_AFTER_DECISION_TIME"] = "STRICTLY_AFTER_DECISION_TIME"
    same_close_fill_allowed: Literal[False] = False
    data_cutoff: Literal["AVAILABLE_BY_DECISION_TIME"] = "AVAILABLE_BY_DECISION_TIME"


class ResearchInvariants(ImmutableContract):
    research_status: Literal["PREREGISTERED_EXPLORATORY_BENCHMARK"] = (
        "PREREGISTERED_EXPLORATORY_BENCHMARK"
    )
    research_classification: Literal["EXPLORATORY_RESEARCH_ONLY"] = "EXPLORATORY_RESEARCH_ONLY"
    qualification_eligible: Literal[False] = False
    profitability_known: Literal[False] = False
    optimized: Literal[False] = False
    literature_replication: Literal[False] = False
    time_basis: TimeBasis = TimeBasis.H1_OBSERVED_BAR


class BenchmarkDefinition(ResearchInvariants):
    schema_version: Literal["benchmark-definition-v0.1.0"] = "benchmark-definition-v0.1.0"
    benchmark_id: BenchmarkId
    family: BenchmarkFamily
    origin_category: OriginCategory
    direction: Direction = Direction.LONG_ONLY
    kernel_semantics: Literal["phase3.1-v0.1.0"] = "phase3.1-v0.1.0"
    entry_rule: EntryRule
    exit_rule: ExitRule
    protective_stop: ProtectiveStopPolicy
    take_profit: TakeProfitPolicy
    decision_timing: DecisionTiming
    required_observations: Period
    pyramiding: Literal[False] = False
    averaging_down: Literal[False] = False
    same_bar_reentry: Literal[False] = False
    short_support: Literal[False] = False
    trailing_stop: Literal[False] = False
    gap_policy: Literal["CONTINUE_OVER_OBSERVED_BARS_WITHOUT_FILLING"] = (
        "CONTINUE_OVER_OBSERVED_BARS_WITHOUT_FILLING"
    )

    @model_validator(mode="after")
    def pinned(self) -> Self:
        actual = (
            self.entry_rule.kind,
            self.entry_rule.fast_ema_period,
            self.entry_rule.slow_ema_period,
            self.entry_rule.previous_high_period,
            self.exit_rule.kind,
            self.exit_rule.previous_low_period,
        )
        expected = {
            BenchmarkId.B01: (
                EntryKind.HYBRID_TREND_AND_BREAKOUT,
                50,
                200,
                20,
                ExitKind.NONE,
                None,
            ),
            BenchmarkId.B02: (
                EntryKind.BULLISH_EMA_CROSS,
                50,
                200,
                None,
                ExitKind.BEARISH_OR_EQUAL_EMA_CROSS,
                None,
            ),
            BenchmarkId.B03: (
                EntryKind.CHANNEL_BREAKOUT,
                None,
                None,
                20,
                ExitKind.CHANNEL_EXIT,
                10,
            ),
            BenchmarkId.B04: (
                EntryKind.CHANNEL_BREAKOUT,
                None,
                None,
                55,
                ExitKind.CHANNEL_EXIT,
                20,
            ),
        }[self.benchmark_id]
        if actual != expected:
            raise ValueError("PREREGISTERED_PARAMETERS_CANNOT_CHANGE")
        legacy = self.benchmark_id == BenchmarkId.B01
        ema_only = self.benchmark_id == BenchmarkId.B02
        family = (
            BenchmarkFamily.LEGACY_HYBRID
            if legacy
            else BenchmarkFamily.MOVING_AVERAGE_TREND
            if ema_only
            else BenchmarkFamily.CHANNEL_TREND
        )
        origin = (
            OriginCategory.PROJECT_LEGACY_HYPOTHESIS
            if legacy
            else OriginCategory.MOVING_AVERAGE_TREND_BENCHMARK
            if ema_only
            else OriginCategory.CHANNEL_TREND_BENCHMARK
        )
        exits = (
            (NormalExit.STOP_LOSS, NormalExit.TAKE_PROFIT)
            if legacy
            else (
                NormalExit.PROTECTIVE_STOP,
                NormalExit.TREND_EXIT if ema_only else NormalExit.CHANNEL_EXIT,
            )
        )
        if (
            self.family != family
            or self.origin_category != origin
            or self.exit_rule.normal_exits != exits
        ):
            raise ValueError("PREREGISTERED_PROVENANCE_OR_EXITS_MISMATCH")
        if self.take_profit.kind != (
            TakeProfitKind.FIXED_PRICE_R_MULTIPLE if legacy else TakeProfitKind.NONE
        ):
            raise ValueError("PREREGISTERED_TP_MISMATCH")
        required = (
            250
            if legacy
            else max(
                self.protective_stop.atr_period,
                (self.entry_rule.slow_ema_period or 0) + (1 if ema_only else 0),
                (self.entry_rule.previous_high_period or 0) + 1,
                (self.exit_rule.previous_low_period or 0) + 1,
            )
        )
        if self.required_observations != required:
            raise ValueError("INCORRECT_DERIVED_WARMUP")
        return self


class BenchmarkRegistry(ResearchInvariants):
    schema_version: Literal["benchmark-registry-v0.1.0"] = "benchmark-registry-v0.1.0"
    definitions: tuple[BenchmarkDefinition, ...]

    @model_validator(mode="after")
    def exact_membership(self) -> Self:
        if tuple(item.benchmark_id for item in self.definitions) != BENCHMARK_ORDER:
            raise ValueError("EXACT_FOUR_BENCHMARKS_IN_CANONICAL_ORDER_REQUIRED")
        return self


class ResearchObservation(ImmutableContract):
    benchmark_id: BenchmarkId
    observed_bar_count: ObservationCount
    bar_close_time: UtcTimestamp
    available_at: UtcTimestamp
    close: Price | None = None
    fast_ema: Price | None = None
    slow_ema: Price | None = None
    previous_high: Price | None = None
    previous_low: Price | None = None

    @model_validator(mode="after")
    def availability(self) -> Self:
        if self.available_at < self.bar_close_time:
            raise ValueError("RESEARCH_VALUES_CANNOT_PRECEDE_COMPLETED_BAR")
        if (
            self.previous_high is not None
            and self.previous_low is not None
            and self.previous_high < self.previous_low
        ):
            raise ValueError("REVERSED_CHANNEL_VALUES")
        return self


class EvaluationInput(ImmutableContract):
    current: ResearchObservation
    previous: ResearchObservation | None = None
    decision_time: UtcTimestamp
    bar_complete: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def chronology(self) -> Self:
        if self.bar_complete and self.decision_time != self.current.bar_close_time:
            raise ValueError("DECISION_MUST_BE_AT_COMPLETED_BAR_CLOSE")
        if self.previous is not None:
            if (
                self.previous.benchmark_id != self.current.benchmark_id
                or self.previous.bar_close_time >= self.current.bar_close_time
                or self.previous.observed_bar_count + 1 != self.current.observed_bar_count
            ):
                raise ValueError("PREVIOUS_MUST_BE_ADJACENT_PRIOR_OBSERVATION")
        return self


class ResearchDecision(StrEnum):
    ENTRY_ELIGIBLE = "ENTRY_ELIGIBLE"
    EXIT_ELIGIBLE = "EXIT_ELIGIBLE"
    HOLD_OR_NO_ACTION = "HOLD_OR_NO_ACTION"
    UNAVAILABLE = "UNAVAILABLE"
