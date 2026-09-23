import ast
import sys
from datetime import timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from tests.mt5.fake import T, instrument, position
from trading_ecosystem.mt5.client import NativeReadClient, ReadError
from trading_ecosystem.mt5.config import BridgeConfig
from trading_ecosystem.mt5.economics import ValidatedCosts, inspect_instrument, to_economics
from trading_ecosystem.mt5.mapping import account_view, position_view
from trading_ecosystem.mt5.normalization import account_identity, normalize, number, timestamp


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "bad", None])
def test_invalid_numbers_fail_closed(value: object) -> None:
    with pytest.raises(ValueError):
        number(value)


def test_decimal_and_utc_milliseconds() -> None:
    assert number(0.1) == Decimal("0.1")
    assert timestamp(0, 1767225600123).isoformat() == "2026-01-01T00:00:00.123000+00:00"
    assert timestamp(1767225600) == timestamp(1767225600, 0)


def test_utc_conversion_ignores_callers_decimal_precision() -> None:
    with localcontext() as context:
        context.prec = 3
        assert timestamp(0, 1767225600123).isoformat() == "2026-01-01T00:00:00.123000+00:00"


@pytest.mark.parametrize("side", [0, 1])
def test_position_copies_identity_metadata_and_unknowns(side: int) -> None:
    row = position(side=side)
    mapped = position_view("scope", row, T, 1)
    assert mapped.side == ("LONG" if side == 0 else "SHORT")
    assert mapped.realized_pnl is None and mapped.quantity == Decimal("0.1")
    assert mapped.episode_id != position_view("another-account", row, T, 1).episode_id
    assert mapped.episode_id != position_view("scope", row, T, 2).episode_id


def test_scoped_account_and_privacy() -> None:
    base = dict(login=1, server="a", company="b")
    assert account_identity(base) != account_identity({**base, "server": "c"})
    assert normalize({"login": 1, "password": object(), "comment": "secret=x"}) == {
        "comment": "[REDACTED]"
    }


@pytest.mark.parametrize(
    "field",
    [
        "trade_tick_size",
        "trade_tick_value",
        "trade_contract_size",
        "volume_min",
        "volume_max",
        "volume_step",
    ],
)
def test_invalid_economics(field: str) -> None:
    data = instrument()
    data[field] = 0
    observed = inspect_instrument("XAUUSD", "TEST.b", data, T, "USD")
    assert observed.status == "INVALID"
    with pytest.raises(ValueError):
        to_economics(observed, None)


def test_economics_partial_and_explicit_reviewed_adapter() -> None:
    observed = inspect_instrument("XAUUSD", "TEST.b", instrument(), T, "USD")
    assert observed.status == "PARTIAL" and observed.sizing_eligible is False
    with pytest.raises(ValueError):
        to_economics(observed, None)
    costs = ValidatedCosts(
        margin_per_lot=Decimal("200"),
        commission_per_lot_per_side=Decimal("3"),
        commission_fixed_per_side=Decimal("0"),
        reference="SYNTHETIC_TEST_REVIEW",
        valid_until=T + timedelta(hours=1),
    )
    mapped = to_economics(observed, costs)
    assert mapped.margin_per_lot == 200 and mapped.minimum_stop_distance == Decimal("0.1")


def test_missing_economics_unavailable_and_non_usd_partial() -> None:
    assert inspect_instrument("XAUUSD", "missing", None, T, "USD").status == "UNAVAILABLE"
    observed = inspect_instrument("XAUUSD", "TEST.b", {}, T, "EUR")
    assert observed.status == "UNAVAILABLE"
    observed = inspect_instrument("XAUUSD", "TEST.b", instrument(), T, "EUR")
    assert "PHASE34_LINEAR_USD_MODEL_NOT_APPLICABLE" in observed.reasons


def test_config_requires_explicit_mapping_and_progressing_window() -> None:
    with pytest.raises(ValidationError):
        BridgeConfig(aliases={})
    with pytest.raises(ValidationError):
        BridgeConfig(aliases={"a": "same", "b": "same"})
    with pytest.raises(ValidationError):
        BridgeConfig(aliases={"a": "a"}, history_window_seconds=60, overlap_seconds=120)


@pytest.mark.parametrize(
    "method",
    [
        "terminal_info",
        "account_info",
        "positions_get",
        "orders_get",
        "symbols_get",
        "symbol_info",
        "symbol_info_tick",
        "history_deals_get",
        "history_orders_get",
    ],
)
def test_native_none_is_error_and_rows_empty_are_valid(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    native: Any = SimpleNamespace(last_error=lambda: (-7, "secret text must not escape"))
    setattr(native, method, lambda *args: None)
    monkeypatch.setitem(sys.modules, "MetaTrader5", native)
    client = NativeReadClient()
    args: tuple[object, ...] = (
        (T, T)
        if method.startswith("history_")
        else (("TEST.b",) if method in {"symbol_info", "symbol_info_tick"} else ())
    )
    with pytest.raises(ReadError, match="MT5_API_ERROR_-7"):
        getattr(client, method)(*args)
    if method.endswith("_get"):
        setattr(native, method, lambda *args: ())
        assert getattr(client, method)(*args) == ()


def test_native_attach_and_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    native = SimpleNamespace(
        initialize=lambda **kwargs: True, shutdown=lambda: calls.append("shutdown")
    )
    monkeypatch.setitem(sys.modules, "MetaTrader5", native)
    client = NativeReadClient()
    assert client.initialize()
    client.shutdown()
    assert calls == ["shutdown"]


def test_read_only_sdk_allowlist_and_lazy_import() -> None:
    allowed = {
        "initialize",
        "shutdown",
        "last_error",
        "terminal_info",
        "account_info",
        "symbols_get",
        "symbol_info",
        "symbol_info_tick",
        "positions_get",
        "orders_get",
        "history_deals_get",
        "history_orders_get",
    }
    from trading_ecosystem.mt5.calculations import CALCULATION_METHODS, READ_METHODS

    assert allowed == READ_METHODS
    assert CALCULATION_METHODS == {"order_calc_profit", "order_calc_margin"}
    allowed |= CALCULATION_METHODS
    forbidden = {
        "order_" + "send",
        "order_check",
        "login",
    }
    for path in Path("src/trading_ecosystem/mt5").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "order_" + "send" not in text
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden
                if isinstance(node.value, ast.Attribute) and node.value.attr == "_sdk":
                    assert node.attr in allowed
            if isinstance(node, ast.Import) and any(n.name == "MetaTrader5" for n in node.names):
                pytest.fail("The frozen discovery SDK loader must remain the sole native import")


def test_unknown_account_totals_never_fabricated() -> None:
    row = dict(balance=1.0, equity=2.0, profit=1.0, margin=0.0, margin_free=2.0)
    view = account_view(row)
    assert view.realized_pnl is None and view.commissions is None and not view.complete
    with pytest.raises(ValidationError):
        type(view).model_validate({**view.model_dump(), "complete": True})
