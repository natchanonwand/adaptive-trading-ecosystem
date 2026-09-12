"""Direct causal calculations with explicit Decimal operation sequences."""

from collections.abc import Sequence
from decimal import Decimal

from trading_ecosystem.datasets.contracts import Bar
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import finite_decimal
from trading_ecosystem.research.indicators.observations import validated_bars


def _period(value: int) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("POSITIVE_INTEGER_PERIOD_REQUIRED")
    return value


def _decimal(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError("DECIMAL_REQUIRED")
    return finite_decimal(value)


def _values(values: Sequence[Decimal]) -> tuple[Decimal, ...]:
    return tuple(_decimal(value) for value in values)


def sma(values: Sequence[Decimal], period: int) -> tuple[Decimal | None, ...]:
    """Trailing mean including the current observed value; period-1 warm-up rows."""
    period = _period(period)
    observations = _values(values)
    result: list[Decimal | None] = []
    with arithmetic_context():
        for index in range(len(observations)):
            result.append(
                None
                if index + 1 < period
                else sum(observations[index - period + 1 : index + 1], Decimal(0)) / Decimal(period)
            )
    return tuple(result)


def ema(values: Sequence[Decimal], period: int) -> tuple[Decimal | None, ...]:
    """SMA seed, then alpha*x + (1-alpha)*previous at each observed value."""
    period = _period(period)
    observations = _values(values)
    if len(observations) < period:
        return (None,) * len(observations)
    result: list[Decimal | None] = [None] * (period - 1)
    with arithmetic_context():
        alpha = Decimal(2) / Decimal(period + 1)
        complement = Decimal(1) - alpha
        previous = sum(observations[:period], Decimal(0)) / Decimal(period)
        result.append(previous)
        for value in observations[period:]:
            previous = alpha * value + complement * previous
            result.append(previous)
    return tuple(result)


def true_range(bars: Sequence[Bar]) -> tuple[Decimal, ...]:
    """First TR is high-low; subsequent TR also measures previous-close distances."""
    observations = validated_bars(bars)
    result = []
    previous: Decimal | None = None
    with arithmetic_context():
        for bar in observations:
            value = bar.high - bar.low
            if previous is not None:
                value = max(value, abs(bar.high - previous), abs(bar.low - previous))
            result.append(value)
            previous = bar.close
    return tuple(result)


def wilder_atr(bars: Sequence[Bar], period: int) -> tuple[Decimal | None, ...]:
    """Mean TR seed; then ((previous*(period-1))+TR)/period without gap resets."""
    period = _period(period)
    ranges = true_range(bars)
    if len(ranges) < period:
        return (None,) * len(ranges)
    result: list[Decimal | None] = [None] * (period - 1)
    with arithmetic_context():
        previous = sum(ranges[:period], Decimal(0)) / Decimal(period)
        result.append(previous)
        for value in ranges[period:]:
            previous = ((previous * Decimal(period - 1)) + value) / Decimal(period)
            result.append(previous)
    return tuple(result)


def previous_high(bars: Sequence[Bar], period: int) -> tuple[Decimal | None, ...]:
    """Maximum of exactly the previous period highs, excluding the current bar."""
    period = _period(period)
    observations = validated_bars(bars)
    return tuple(
        None if index < period else max(bar.high for bar in observations[index - period : index])
        for index in range(len(observations))
    )


def previous_low(bars: Sequence[Bar], period: int) -> tuple[Decimal | None, ...]:
    """Minimum of exactly the previous period lows, excluding the current bar."""
    period = _period(period)
    observations = validated_bars(bars)
    return tuple(
        None if index < period else min(bar.low for bar in observations[index - period : index])
        for index in range(len(observations))
    )


def trailing_return(close: Sequence[Decimal], lookback: int) -> tuple[Decimal | None, ...]:
    """Fractional observed-close change (current-previous)/previous; no annualization."""
    lookback = _period(lookback)
    observations = _values(close)
    if any(value <= 0 for value in observations):
        raise ValueError("POSITIVE_CLOSE_REQUIRED")
    result: list[Decimal | None] = []
    with arithmetic_context():
        for index, value in enumerate(observations):
            result.append(
                None
                if index < lookback
                else (value - observations[index - lookback]) / observations[index - lookback]
            )
    return tuple(result)
