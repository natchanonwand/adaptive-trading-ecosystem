"""Calibration failures must not become qualification or execution authority."""

import ast
import sys
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.mt5.fake import T, deal, instrument
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.mt5.calculations import (
    CALCULATION_METHODS,
    FORBIDDEN_TRADING_METHODS,
    NativeCalculator,
    Side,
    action,
)
from trading_ecosystem.mt5.calibration import require_demo
from trading_ecosystem.mt5.calibration_economics import (
    BrokerEconomicsEvidence,
    conditional_economics,
    constraints,
    qualified_economics,
    valid_volume,
)
from trading_ecosystem.mt5.calibration_matrix import calibrate_symbol
from trading_ecosystem.mt5.calibration_verify import RecordedCalculator
from trading_ecosystem.mt5.client import ReadError, Record
from trading_ecosystem.mt5.cost_profile import distribution, profile_deals, profile_spreads
from trading_ecosystem.mt5.economics import BrokerInstrumentSnapshot, inspect_instrument
from trading_ecosystem.mt5.normalization import normalize

D = Decimal


def snapshot(asset: str = "BTCUSD", **updates: Any) -> BrokerInstrumentSnapshot:
    row = instrument()
    row.update(
        trade_tick_value=".01",
        trade_tick_value_profit=".01",
        trade_tick_value_loss=".01",
        trade_contract_size="1",
        trade_stops_level=0,
    )
    if asset == "XAUUSD":
        row.update(
            digits=3,
            point=".001",
            trade_tick_size=".001",
            trade_tick_value=".1",
            trade_tick_value_profit=".1",
            trade_tick_value_loss=".1",
            trade_contract_size="100",
        )
    if asset == "USTEC100":
        row.update(volume_min=".05")
    row.update(updates)
    return inspect_instrument(asset, asset + ".demo", row, T, "USD")


class LinearCalculator:
    def __init__(self, contract: Decimal) -> None:
        self.contract = contract

    def profit(
        self, side: Side, symbol: str, volume: Decimal, opened: Decimal, closed: Decimal
    ) -> Decimal:
        with arithmetic_context():
            sign = 1 if side == "BUY" else -1
            return (sign * (closed - opened) * volume * self.contract).quantize(
                D(".01"), rounding=ROUND_HALF_UP
            )

    def margin(self, side: Side, symbol: str, volume: Decimal, price: Decimal) -> Decimal:
        with arithmetic_context():
            return (volume * price * self.contract / 2000).quantize(D(".01"), ROUND_HALF_UP)


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("method", ["profit", "margin"])
def test_native_calculator_decimal_boundary(
    monkeypatch: pytest.MonkeyPatch, side: Side, method: str
) -> None:
    calls: list[tuple[Any, ...]] = []

    def calc(*args: Any) -> float:
        calls.append(args)
        return -0.31 if method == "profit" else 0.31

    sdk: Any = SimpleNamespace(order_calc_profit=calc, order_calc_margin=calc)
    monkeypatch.setitem(sys.modules, "MetaTrader5", sdk)
    client = NativeCalculator()
    args = (side, "DEMO", D(".05"), D("100.01"))
    result = client.profit(*args, D("99.01")) if method == "profit" else client.margin(*args)
    assert result == D("-.31" if method == "profit" else ".31")
    assert calls[0][0] == (0 if side == "BUY" else 1)
    assert all(type(v) is float for v in calls[0][2:])


@pytest.mark.parametrize("method", ["profit", "margin"])
@pytest.mark.parametrize("failure", ["none", "exception", "nan"])
def test_calculator_failures(monkeypatch: pytest.MonkeyPatch, method: str, failure: str) -> None:
    def calc(*args: Any) -> Any:
        if failure == "exception":
            raise RuntimeError("private native text")
        return None if failure == "none" else float("nan")

    monkeypatch.setitem(
        sys.modules,
        "MetaTrader5",
        SimpleNamespace(
            order_calc_profit=calc, order_calc_margin=calc, last_error=lambda: (-1, "private")
        ),
    )
    client = NativeCalculator()
    with pytest.raises((ReadError, ValueError)) as error:
        if method == "profit":
            client.profit("BUY", "DEMO", D(1), D(100), D(99))
        else:
            client.margin("SELL", "DEMO", D(1), D(100))
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "asset,price", [("BTCUSD", "100000"), ("XAUUSD", "4000"), ("USTEC100", "25000")]
)
def test_complete_pure_matrix(asset: str, price: str) -> None:
    snap = snapshot(asset)
    calculator = LinearCalculator(D(snap.metadata["trade_contract_size"]))
    result = calibrate_symbol(calculator, snap, {"bid": price, "ask": price}, 2, D(0))
    assert result["profit_calculation_count"] == 48
    assert len(result["margin_rows"]) == 8
    rows = result["risk_rows"]
    assert len(rows) == 48
    assert any(r["accepted"] for r in rows)
    for row in rows:
        if row["policy"] == "V0_CONSERVATIVE" and row["side"] == "SELL":
            assert not row["accepted"] and "V0_LONG_ONLY" in row["reasons"]
        if row["accepted"]:
            assert D(row["broker_loss"]) <= D(row["risk_budget"]) + D(row["tolerance"])
            assert D(row["predicted_loss"]) <= D(row["risk_budget"])
            assert valid_volume(D(row["selected_volume"]), snap)
            assert not row["within_observed_free_margin"]
        if row["equity"] == "300" and row["stop_ticks"] == 200000:
            assert not row["accepted"]
            assert D(row["minimum_lot_broker_loss"]) > D(row["risk_budget"])
    assert any(r["accepted"] and r["policy"] == "HR_DEMO_5PCT" for r in rows)


@pytest.mark.parametrize(
    "field,value",
    [
        ("trade_tick_value_loss", "2"),
        ("trade_contract_size", "0"),
        ("volume_step", "0"),
        ("trade_tick_size", "-1"),
    ],
)
def test_incompatible_economics_refused(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        conditional_economics(snapshot(**{field: value}), D(1))


@pytest.mark.parametrize(
    "value,expected",
    [(".05", True), (".06", True), (".055", False), (".01", False), ("101", False)],
)
def test_minimum_anchored_volume_lattice(value: str, expected: bool) -> None:
    assert valid_volume(D(value), snapshot("USTEC100")) is expected


@pytest.mark.parametrize("field", ["margin_estimate", "commission_model", "swap_model"])
def test_missing_evidence_cannot_admit_sizing(field: str) -> None:
    fields: Record = dict(
        price_pnl_model="VALIDATED",
        volume_lattice="VALIDATED",
        tick_economics="VALIDATED",
        margin_estimate="VALIDATED",
        commission_model="VALIDATED",
        swap_model="VALIDATED",
        stop_constraints="VALIDATED",
    )
    fields[field] = "UNKNOWN"
    evidence = BrokerEconomicsEvidence(snapshot=snapshot(), **fields)
    assert not evidence.risk_sizing_ready
    with pytest.raises(ValueError, match="NOT_SIZING_READY"):
        qualified_economics(evidence, None)


@pytest.mark.parametrize(
    "field,value",
    [("digits", 1), ("trade_stops_level", -1), ("trade_freeze_level", "1.5"), ("point", "0")],
)
def test_invalid_stop_metadata(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        constraints(snapshot(**{field: value}))


def test_cost_sample_is_not_contract_and_duplicates_do_not_inflate() -> None:
    one, two = normalize(deal()), normalize(deal(2))
    one.update(commission="0", fee="0", swap="0")
    two.update(commission="-.2", fee="-.1", swap="-.3")
    result = profile_deals([one, two, one])
    assert result["deal_count"] == 2 and result["duplicate_count"] == 1
    assert not result["contractually_validated"]
    group = result["groups"][0]
    for field in ("commission", "fee", "swap"):
        assert group[field]["nonzero_count"] == 1
    assert D(group["commission"]["per_lot"]["minimum"]) == -2
    assert D(group["commission"]["per_lot"]["median"]) == -1
    assert profile_deals([one])["groups"][0]["commission"]["observed_zero_in_current_sample"]
    with pytest.raises(ValueError, match="CONFLICTING"):
        profile_deals([one, {**one, "fee": "1"}])


def test_missing_costs_remain_unknown_and_nontrade_volume_not_divided() -> None:
    row = normalize(deal())
    row.update(commission=None, volume="0")
    group = profile_deals([row])["groups"][0]
    assert group["commission"]["classification"] == "UNKNOWN"
    assert group["commission"]["missing_count"] == 1
    assert group["swap"]["per_lot"]["sample_count"] == 0


def test_decimal_spreads_percentiles_and_sample_deduplication() -> None:
    quotes = [("A", {"bid": "10", "ask": str(D(10) + D(i) / 100)}) for i in range(1, 21)]
    result = profile_spreads(quotes + quotes)["symbols"]["A"]
    assert result["sample_count"] == 20
    assert D(result["median"]) == D(".105")
    assert D(result["p90"]) == D(".18")
    assert D(result["p95"]) == D(".19")
    assert distribution([])["median"] is None
    with pytest.raises(ValueError, match="CROSSED"):
        profile_spreads([("A", {"bid": "2", "ask": "1"})])


@pytest.mark.parametrize(
    "account",
    [
        {"trade_mode": 2},
        {"trade_mode": False},
        {"trade_mode": 0, "currency": "EUR"},
        {"trade_mode": 0, "currency": "USD"},
    ],
)
def test_demo_and_precision_required(account: Record) -> None:
    with pytest.raises(ValueError):
        require_demo(account, {"connected": True})


def test_no_broker_request_and_no_reservation_persistence() -> None:
    assert CALCULATION_METHODS == {"order_calc_profit", "order_calc_margin"}
    assert "order_" + "send" in FORBIDDEN_TRADING_METHODS
    for path in Path("src/trading_ecosystem/mt5").glob("cal*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                )
                assert name not in {"evaluate_and_reserve", "OrderSendRequest", "MqlTradeRequest"}
                assert name not in FORBIDDEN_TRADING_METHODS
    with pytest.raises(ValueError):
        action("INVALID")  # type: ignore[arg-type]


def test_monetary_leg_rounding_and_independent_replay() -> None:
    class Legs(LinearCalculator):
        def profit(
            self, side: Side, symbol: str, volume: Decimal, opened: Decimal, closed: Decimal
        ) -> Decimal:
            with arithmetic_context():
                return (
                    (closed * volume).quantize(D(".01"), ROUND_HALF_UP)
                    - (opened * volume).quantize(D(".01"), ROUND_HALF_UP)
                ) * (1 if side == "BUY" else -1)

    snap = snapshot()
    quote = {"bid": "86140.88", "ask": "86140.88"}
    result = calibrate_symbol(Legs(D(1)), snap, quote, 2, D(0))
    replay = calibrate_symbol(RecordedCalculator(result), snap, quote, 2, D(0))
    assert result == replay
    result["risk_rows"][0]["minimum_lot_broker_loss"] = "9999"
    with pytest.raises(ValueError):
        calibrate_symbol(RecordedCalculator(result), snap, quote, 2, D(0))


def test_broker_risk_breach_is_failure() -> None:
    class BadLoss(LinearCalculator):
        def profit(
            self, side: Side, symbol: str, volume: Decimal, opened: Decimal, closed: Decimal
        ) -> Decimal:
            result = super().profit(side, symbol, volume, opened, closed)
            return result * 1000 if abs(opened - closed) >= 100 and volume > D(".01") else result

    with pytest.raises(ValueError, match="BROKER_STOP_LOSS_EXCEEDS"):
        calibrate_symbol(BadLoss(D(1)), snapshot(), {"bid": "100000", "ask": "100000"}, 2, D(0))


def test_nonlinear_margin_cannot_be_claimed_validated() -> None:
    class Nonlinear(LinearCalculator):
        def margin(self, side: Side, symbol: str, volume: Decimal, price: Decimal) -> Decimal:
            return volume * volume * 100

    with pytest.raises(ValueError, match="NONLINEAR_MARGIN"):
        calibrate_symbol(Nonlinear(D(1)), snapshot(), {"bid": "100000", "ask": "100000"}, 2, D(0))


def test_nonmidnight_capture_has_explicit_simulated_utc_day_baseline() -> None:
    snap = snapshot().model_copy(update={"observed_at": T + timedelta(hours=13)})
    result = calibrate_symbol(
        LinearCalculator(D(1)), snap, {"bid": "100000", "ask": "100001"}, 2, D(0)
    )
    assert any(r["accepted"] for r in result["risk_rows"])
    assert all("UNKNOWN_NAV_OR_DAILY_BASELINE" not in r["reasons"] for r in result["risk_rows"])
