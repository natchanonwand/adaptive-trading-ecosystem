"""Research eligibility only, from explicitly supplied current/prior values."""

from trading_ecosystem.benchmarks.contracts import BenchmarkId, EvaluationInput, ResearchDecision
from trading_ecosystem.benchmarks.registry import get_definition
from trading_ecosystem.research.indicators import (
    ChannelState,
    MovingAverageState,
    channel_breakout_state,
    moving_average_state,
)


def evaluate(inputs: EvaluationInput) -> ResearchDecision:
    inputs = EvaluationInput.model_validate(inputs)
    current = inputs.current
    definition = get_definition(current.benchmark_id)
    if (
        not inputs.bar_complete
        or current.available_at > inputs.decision_time
        or current.observed_bar_count < definition.required_observations
    ):
        return ResearchDecision.UNAVAILABLE
    if current.benchmark_id == BenchmarkId.B01:
        trend = moving_average_state(current.fast_ema, current.slow_ema)
        # A degenerate channel tests the upper boundary without requiring an unused low.
        channel = channel_breakout_state(
            current.close, current.previous_high, current.previous_high
        )
        if trend == MovingAverageState.UNAVAILABLE or channel == ChannelState.UNAVAILABLE:
            return ResearchDecision.UNAVAILABLE
        return (
            ResearchDecision.ENTRY_ELIGIBLE
            if trend == MovingAverageState.BULLISH and channel == ChannelState.UPSIDE_BREAKOUT
            else ResearchDecision.HOLD_OR_NO_ACTION
        )
    if current.benchmark_id == BenchmarkId.B02:
        previous = inputs.previous
        if previous is None or previous.available_at > inputs.decision_time:
            return ResearchDecision.UNAVAILABLE
        now = moving_average_state(current.fast_ema, current.slow_ema)
        before = moving_average_state(previous.fast_ema, previous.slow_ema)
        if MovingAverageState.UNAVAILABLE in (before, now):
            return ResearchDecision.UNAVAILABLE
        if before != MovingAverageState.BULLISH and now == MovingAverageState.BULLISH:
            return ResearchDecision.ENTRY_ELIGIBLE
        if before == MovingAverageState.BULLISH and now != MovingAverageState.BULLISH:
            return ResearchDecision.EXIT_ELIGIBLE
        return ResearchDecision.HOLD_OR_NO_ACTION
    channel = channel_breakout_state(current.close, current.previous_high, current.previous_low)
    if channel == ChannelState.UNAVAILABLE:
        return ResearchDecision.UNAVAILABLE
    if channel == ChannelState.UPSIDE_BREAKOUT:
        return ResearchDecision.ENTRY_ELIGIBLE
    if channel == ChannelState.DOWNSIDE_BREAKOUT:
        return ResearchDecision.EXIT_ELIGIBLE
    return ResearchDecision.HOLD_OR_NO_ACTION
