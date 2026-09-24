from decimal import Decimal, localcontext

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trading_ecosystem.features.indicators import (
    atr,
    ema,
    quantile,
    range_measurements,
    returns,
    rsi,
    std,
)


def test_ema_known_seed_and_recursive_values() -> None:
    assert ema(list(map(Decimal, [1, 2, 3, 4, 5])), 3) == 4
    assert ema([Decimal(1)] * 199, 200) is None
    assert ema([Decimal(1)] * 200, 200) == 1
    with localcontext() as context:
        context.prec = 4
        assert ema(list(map(Decimal, [1, 2, 3, 4, 5])), 3) == 4


def test_atr_wilder_known_fixture() -> None:
    bars = [dict(high="11", low="9", close="10")] * 15 + [dict(high="14", low="10", close="12")]
    with localcontext() as c:
        c.prec = 34
        assert atr(bars) == Decimal(30) / 14
    assert atr(bars[:14]) is None


def test_rsi_wilder_known_gain_loss_and_flat() -> None:
    assert rsi([Decimal(i) for i in range(15)]) == 100
    assert rsi([Decimal(20 - i) for i in range(15)]) == 0
    assert rsi([Decimal(10)] * 15) == 50
    # Seven gains of 2 and seven losses of 1: average gain twice average loss.
    prices = [Decimal(10)]
    for i in range(14):
        prices.append(prices[-1] + (2 if i % 2 == 0 else -1))
    strength = rsi(prices)
    assert strength is not None
    assert abs(strength - Decimal("66.66666666666666666666666666666667")) < Decimal("1e-30")
    assert rsi(prices[:14]) is None


def test_returns_ranges_std_and_quantiles() -> None:
    assert returns([Decimal(100), Decimal(110)], 1) == Decimal(".1")
    assert returns([Decimal(100)], 1) is None
    bars = [dict(high="12", low="8"), dict(high="12", low="9")]
    value = range_measurements(bars, 2, Decimal(10))
    assert value["range"] == 4 and value["range_position"] == Decimal(".5")
    assert value["bars_since_high"] == 0 and value["bars_since_low"] == 1
    assert std(list(map(Decimal, [1, 1]))) == 0
    assert quantile(list(map(Decimal, [0, 10])), Decimal(".25")) == Decimal("2.5")


@given(st.lists(st.integers(min_value=1, max_value=10000), min_size=20, max_size=60))
def test_ema_convex_hull_and_rsi_bounds(values: list[int]) -> None:
    decimals = list(map(Decimal, values))
    average = ema(decimals, 20)
    strength = rsi(decimals)
    assert average is not None and min(decimals) <= average <= max(decimals)
    assert strength is not None and 0 <= strength <= 100


@pytest.mark.parametrize("period", [0, -1])
def test_invalid_period_rejected(period: int) -> None:
    with pytest.raises(ValueError):
        ema([], period)
