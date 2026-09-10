from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from trading_ecosystem.domain.arithmetic import (
    ARITHMETIC_VERSION,
    arithmetic_context,
    lot_step_floor,
    nearest_permitted_tick,
    price_tick_ceiling,
    price_tick_floor,
)
from trading_ecosystem.domain.primitives import (
    AccountSequence,
    Asset,
    CausationId,
    CorrelationId,
    EntityId,
    MoneyAmount,
    PriceAmount,
    QuantityAmount,
    RuntimeMode,
    UtcTimestamp,
    positive_decimal,
)


def test_assets_and_modes() -> None:
    assert {asset.value for asset in Asset} == {"BTCUSD", "XAUUSD", "USTEC100"}
    assert {mode.value for mode in RuntimeMode} == {
        "RESEARCH",
        "BACKTEST",
        "PAPER_FORWARD",
        "DEMO_QUALIFICATION",
        "DEMO_OPERATIONAL",
    }
    with pytest.raises(ValueError):
        Asset("EURUSD")
    with pytest.raises(ValueError):
        RuntimeMode("LIVE")


def test_utc_enforcement() -> None:
    adapter = TypeAdapter(UtcTimestamp)
    with pytest.raises(ValidationError):
        adapter.validate_python(datetime(2026, 1, 1))
    with pytest.raises(ValidationError):
        adapter.validate_python("2026-01-01T00:00:00")
    bangkok = datetime(2026, 9, 10, 1, tzinfo=timezone(timedelta(hours=7)))
    assert adapter.validate_python(bangkok) == datetime(2026, 9, 9, 18, tzinfo=UTC)
    assert adapter.validate_python(bangkok).tzinfo is UTC


@pytest.mark.parametrize("alias", [EntityId, CorrelationId, CausationId])
def test_identifiers(alias: object) -> None:
    adapter: TypeAdapter[Any] = TypeAdapter(alias)
    value = uuid4()
    assert adapter.validate_python(str(value)) == value
    with pytest.raises(ValidationError):
        adapter.validate_python("not-an-id")


@pytest.mark.parametrize("bad", [True, 0, -1, 1.0, "1", 2**63])
def test_sequence_rejections(bad: object) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(AccountSequence).validate_python(bad)


@pytest.mark.parametrize("bad", [0.1, True, "NaN", "Infinity", "-Infinity", "1e101"])
def test_money_rejects_invalid_input(bad: object) -> None:
    with pytest.raises(ValidationError):
        MoneyAmount.model_validate({"amount": bad, "currency": "USD"})


def test_amount_units_and_immutability() -> None:
    money = MoneyAmount(amount=Decimal("-1.25"), currency="USD")
    assert money.amount == Decimal("-1.25")
    with pytest.raises(ValidationError):
        money.amount = Decimal(2)  # type: ignore[misc]
    assert PriceAmount(value=Decimal(1), asset=Asset.BTCUSD).value == 1
    assert QuantityAmount(value=Decimal(".01"), unit="lot").unit == "lot"
    with pytest.raises(ValidationError):
        PriceAmount(value=Decimal(0), asset=Asset.BTCUSD)
    with pytest.raises(ValidationError):
        MoneyAmount(amount=Decimal(1), currency="usd")


def test_arithmetic_context_is_isolated() -> None:
    with localcontext() as outer:
        outer.prec = 6
        with arithmetic_context() as context:
            assert context.prec == 34
            assert context.rounding == ROUND_HALF_EVEN
            assert Decimal("2.5").quantize(Decimal(1)) == 2
            assert Decimal("3.5").quantize(Decimal(1)) == 4
        assert outer.prec == 6
    assert ARITHMETIC_VERSION == "decimal34-half-even-v1"


def test_tick_and_lot_boundaries() -> None:
    assert price_tick_floor("120.045", ".01") == Decimal("120.04")
    assert price_tick_ceiling("120.045", ".01") == Decimal("120.05")
    assert lot_step_floor("1.239", ".05") == Decimal("1.20")
    assert nearest_permitted_tick("1.025", ".05") == Decimal("1.00")
    assert nearest_permitted_tick("1.075", ".05") == Decimal("1.10")
    assert price_tick_floor(".01", ".05") == 0
    with localcontext() as context:
        context.prec = 2
        assert price_tick_floor("120.045", ".01") == Decimal("120.04")


@pytest.mark.parametrize("bad", [0, -1, 0.1, "NaN", "Infinity", True])
def test_positive_conversion(bad: object) -> None:
    with pytest.raises(ValueError):
        positive_decimal(bad)
