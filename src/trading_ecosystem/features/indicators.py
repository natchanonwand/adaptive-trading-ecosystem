"""Decimal34 indicators with explicit finite-window seeds and missing-history rules."""

from decimal import Decimal

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import number


def mean(values: list[Decimal]) -> Decimal | None:
    with arithmetic_context():
        return sum(values, Decimal(0)) / len(values) if values else None


def quantile(values: list[Decimal], probability: Decimal) -> Decimal | None:
    if not values:
        return None
    with arithmetic_context():
        ordered = sorted(values)
        index = (len(ordered) - 1) * probability
        lower = int(index)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def std(values: list[Decimal]) -> Decimal | None:
    average = mean(values)
    with arithmetic_context():
        return (
            (sum(((v - average) ** 2 for v in values), Decimal(0)) / len(values)).sqrt()
            if average is not None
            else None
        )


def ema(values: list[Decimal], period: int) -> Decimal | None:
    if period < 1:
        raise ValueError("INVALID_PERIOD")
    if len(values) < period:
        return None
    with arithmetic_context():
        result = sum(values[:period], Decimal(0)) / period
        alpha = Decimal(2) / (period + 1)
        for value in values[period:]:
            result += alpha * (value - result)
        return result


def wilder(values: list[Decimal], period: int) -> Decimal | None:
    if period < 1:
        raise ValueError("INVALID_PERIOD")
    if len(values) < period:
        return None
    with arithmetic_context():
        result = sum(values[:period], Decimal(0)) / period
        for value in values[period:]:
            result = ((period - 1) * result + value) / period
        return result


def atr(bars: list[Record], period: int = 14) -> Decimal | None:
    with arithmetic_context():
        true_ranges = [
            max(
                number(b["high"]) - number(b["low"]),
                abs(number(b["high"]) - number(a["close"])),
                abs(number(b["low"]) - number(a["close"])),
            )
            for a, b in zip(bars, bars[1:], strict=False)
        ]
        return wilder(true_ranges, period)


def rsi(values: list[Decimal], period: int = 14) -> Decimal | None:
    with arithmetic_context():
        changes = [b - a for a, b in zip(values, values[1:], strict=False)]
        gain = wilder([max(v, Decimal(0)) for v in changes], period)
        loss = wilder([max(-v, Decimal(0)) for v in changes], period)
        if gain is None or loss is None:
            return None
        if loss == 0:
            return Decimal(100) if gain else Decimal(50)
        return 100 - 100 / (1 + gain / loss)


def returns(values: list[Decimal], lag: int) -> Decimal | None:
    if lag < 1:
        raise ValueError("INVALID_LAG")
    with arithmetic_context():
        return (
            values[-1] / values[-1 - lag] - 1
            if len(values) > lag and values[-1 - lag] > 0
            else None
        )


def range_measurements(bars: list[Record], count: int, price: Decimal | None) -> Record:
    names = (
        "range",
        "distance_high",
        "distance_low",
        "range_position",
        "bars_since_high",
        "bars_since_low",
    )
    if len(bars) < count:
        return dict.fromkeys(names)
    selected = bars[-count:]
    highs, lows = [number(b["high"]) for b in selected], [number(b["low"]) for b in selected]
    high, low = max(highs), min(lows)
    with arithmetic_context():
        return dict(
            range=high - low,
            distance_high=high - price if price is not None else None,
            distance_low=price - low if price is not None else None,
            range_position=(price - low) / (high - low)
            if price is not None and high > low
            else None,
            bars_since_high=next(i for i, v in enumerate(reversed(highs)) if v == high),
            bars_since_low=next(i for i, v in enumerate(reversed(lows)) if v == low),
        )
