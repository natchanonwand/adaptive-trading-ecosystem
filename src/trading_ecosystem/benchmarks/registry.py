"""Exactly four pinned preregistered hypotheses, in explicit canonical order."""

from trading_ecosystem.benchmarks.contracts import (
    BenchmarkDefinition,
    BenchmarkFamily,
    BenchmarkId,
    BenchmarkRegistry,
    DecisionTiming,
    EntryKind,
    EntryRule,
    ExitKind,
    ExitRule,
    NormalExit,
    OriginCategory,
    ProtectiveStopPolicy,
    TakeProfitKind,
    TakeProfitPolicy,
)


def _definition(
    benchmark_id: BenchmarkId,
    family: BenchmarkFamily,
    origin: OriginCategory,
    entry: EntryRule,
    exit_rule: ExitRule,
    warmup: int,
) -> BenchmarkDefinition:
    take_profit = TakeProfitPolicy(kind=TakeProfitKind.NONE)
    if benchmark_id == BenchmarkId.B01:
        take_profit = TakeProfitPolicy(
            kind=TakeProfitKind.FIXED_PRICE_R_MULTIPLE,
            r_multiple=2,
            initial_price_risk_basis="ACTUAL_SIMULATED_ENTRY_FILL_MINUS_FIXED_STOP",
            target_basis="ACTUAL_SIMULATED_ENTRY_FILL_PLUS_R_MULTIPLE_OF_INITIAL_PRICE_RISK",
        )
    return BenchmarkDefinition(
        benchmark_id=benchmark_id,
        family=family,
        origin_category=origin,
        entry_rule=entry,
        exit_rule=exit_rule,
        required_observations=warmup,
        protective_stop=ProtectiveStopPolicy(),
        take_profit=take_profit,
        decision_timing=DecisionTiming(),
    )


REGISTRY = BenchmarkRegistry(
    definitions=(
        _definition(
            BenchmarkId.B01,
            BenchmarkFamily.LEGACY_HYBRID,
            OriginCategory.PROJECT_LEGACY_HYPOTHESIS,
            EntryRule(
                kind=EntryKind.HYBRID_TREND_AND_BREAKOUT,
                fast_ema_period=50,
                slow_ema_period=200,
                previous_high_period=20,
            ),
            ExitRule(
                kind=ExitKind.NONE, normal_exits=(NormalExit.STOP_LOSS, NormalExit.TAKE_PROFIT)
            ),
            250,
        ),
        _definition(
            BenchmarkId.B02,
            BenchmarkFamily.MOVING_AVERAGE_TREND,
            OriginCategory.MOVING_AVERAGE_TREND_BENCHMARK,
            EntryRule(kind=EntryKind.BULLISH_EMA_CROSS, fast_ema_period=50, slow_ema_period=200),
            ExitRule(
                kind=ExitKind.BEARISH_OR_EQUAL_EMA_CROSS,
                normal_exits=(NormalExit.PROTECTIVE_STOP, NormalExit.TREND_EXIT),
            ),
            201,
        ),
        _definition(
            BenchmarkId.B03,
            BenchmarkFamily.CHANNEL_TREND,
            OriginCategory.CHANNEL_TREND_BENCHMARK,
            EntryRule(kind=EntryKind.CHANNEL_BREAKOUT, previous_high_period=20),
            ExitRule(
                kind=ExitKind.CHANNEL_EXIT,
                previous_low_period=10,
                normal_exits=(NormalExit.PROTECTIVE_STOP, NormalExit.CHANNEL_EXIT),
            ),
            21,
        ),
        _definition(
            BenchmarkId.B04,
            BenchmarkFamily.CHANNEL_TREND,
            OriginCategory.CHANNEL_TREND_BENCHMARK,
            EntryRule(kind=EntryKind.CHANNEL_BREAKOUT, previous_high_period=55),
            ExitRule(
                kind=ExitKind.CHANNEL_EXIT,
                previous_low_period=20,
                normal_exits=(NormalExit.PROTECTIVE_STOP, NormalExit.CHANNEL_EXIT),
            ),
            56,
        ),
    )
)


def get_definition(benchmark_id: BenchmarkId) -> BenchmarkDefinition:
    benchmark_id = BenchmarkId(benchmark_id)
    return next(item for item in REGISTRY.definitions if item.benchmark_id == benchmark_id)
