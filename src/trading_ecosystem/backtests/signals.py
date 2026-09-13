"""Causal orchestration of unchanged Phase 3.1 values and Phase 3.2 decisions."""

from decimal import Decimal

from trading_ecosystem.benchmarks.contracts import (
    BenchmarkDefinition,
    EvaluationInput,
    ResearchDecision,
    ResearchObservation,
)
from trading_ecosystem.benchmarks.rules import evaluate
from trading_ecosystem.datasets.contracts import Bar
from trading_ecosystem.research import indicators as k


def signals(bars: tuple[Bar, ...], definition: BenchmarkDefinition) -> tuple[ResearchDecision, ...]:
    close = k.observed_closes(bars)
    rule = definition.entry_rule
    empty: tuple[Decimal | None, ...] = (None,) * len(bars)
    fast = k.ema(close, rule.fast_ema_period) if rule.fast_ema_period else empty
    slow = k.ema(close, rule.slow_ema_period) if rule.slow_ema_period else empty
    high = k.previous_high(bars, rule.previous_high_period) if rule.previous_high_period else empty
    low_period = definition.exit_rule.previous_low_period
    low = k.previous_low(bars, low_period) if low_period else empty
    previous = None
    decisions = []
    for index, bar in enumerate(bars):
        current = ResearchObservation(
            benchmark_id=definition.benchmark_id,
            observed_bar_count=index + 1,
            bar_close_time=bar.close_time,
            available_at=bar.available_at,
            close=bar.close,
            fast_ema=fast[index],
            slow_ema=slow[index],
            previous_high=high[index],
            previous_low=low[index],
        )
        decisions.append(
            evaluate(
                EvaluationInput(
                    current=current,
                    previous=previous,
                    decision_time=bar.close_time,
                    bar_complete=True,
                )
            )
        )
        previous = current
    return tuple(decisions)
