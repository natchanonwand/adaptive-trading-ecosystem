"""Stateless mathematical benchmark classifications."""

from decimal import Decimal
from enum import StrEnum

from trading_ecosystem.research.indicators.core import _decimal


class MovingAverageState(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNAVAILABLE = "UNAVAILABLE"


class ChannelState(StrEnum):
    UPSIDE_BREAKOUT = "UPSIDE_BREAKOUT"
    DOWNSIDE_BREAKOUT = "DOWNSIDE_BREAKOUT"
    INSIDE = "INSIDE"
    UNAVAILABLE = "UNAVAILABLE"


class MomentumState(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    FLAT = "FLAT"
    UNAVAILABLE = "UNAVAILABLE"


def _optional(value: Decimal | None) -> Decimal | None:
    return None if value is None else _decimal(value)


def moving_average_state(fast_ma: Decimal | None, slow_ma: Decimal | None) -> MovingAverageState:
    fast, slow = _optional(fast_ma), _optional(slow_ma)
    if fast is None or slow is None:
        return MovingAverageState.UNAVAILABLE
    if fast > slow:
        return MovingAverageState.BULLISH
    if fast < slow:
        return MovingAverageState.BEARISH
    return MovingAverageState.NEUTRAL


def channel_breakout_state(
    close: Decimal | None,
    previous_high: Decimal | None,
    previous_low: Decimal | None,
) -> ChannelState:
    value, high, low = _optional(close), _optional(previous_high), _optional(previous_low)
    if high is not None and low is not None and high < low:
        raise ValueError("INVALID_CHANNEL_BOUNDS")
    if value is None or high is None or low is None:
        return ChannelState.UNAVAILABLE
    if value > high:
        return ChannelState.UPSIDE_BREAKOUT
    if value < low:
        return ChannelState.DOWNSIDE_BREAKOUT
    return ChannelState.INSIDE


def momentum_state(trailing_return: Decimal | None) -> MomentumState:
    value = _optional(trailing_return)
    if value is None:
        return MomentumState.UNAVAILABLE
    if value > 0:
        return MomentumState.POSITIVE
    if value < 0:
        return MomentumState.NEGATIVE
    return MomentumState.FLAT
