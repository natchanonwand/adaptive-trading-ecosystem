"""Hand-calculated USD fixtures and arithmetic conservation properties."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal, Inexact, localcontext
from typing import Any
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from trading_ecosystem.accounting.contracts import (
    AccountInput,
    Category,
    LedgerEntry,
    LongPosition,
    Reservation,
    UsdValuationModel,
)
from trading_ecosystem.accounting.performance import project_portfolio
from trading_ecosystem.accounting.projection import project_balance, project_equity
from trading_ecosystem.domain.primitives import Asset

D = Decimal
T = datetime(2026, 9, 14, tzinfo=UTC)
ACCOUNT = UUID(int=1)


def entry(
    amount: str = "10",
    category: Category = Category.REALIZED_PNL,
    sequence: int = 1,
    at: datetime = T + timedelta(hours=1),
    **updates: Any,
) -> LedgerEntry:
    return LedgerEntry.model_validate(
        {
            "entry_id": UUID(int=100 + sequence),
            "account_id": ACCOUNT,
            "sequence": sequence,
            "amount": amount,
            "category": category,
            "reference_id": UUID(int=10),
            "effective_at": at,
            "recorded_at": at,
            **updates,
        }
    )


def account(at: datetime = T, **updates: Any) -> AccountInput:
    return AccountInput.model_validate(
        {
            "account_id": ACCOUNT,
            "opening_at": T,
            "opening_cash": "1000",
            "valuation_at": at,
            "reconciled_at": at,
            **updates,
        }
    )


def position(asset: Asset = Asset.BTCUSD, **updates: Any) -> LongPosition:
    model = UsdValuationModel(
        model_id="synthetic-linear-fixture",
        instrument_id=asset.value,
        asset=asset,
        quantity_unit="lot",
        price_unit="USD-price-point",
        usd_per_quantity_price_unit=D("10"),
        valid_from=T - timedelta(days=1),
        valid_until=T + timedelta(days=10),
        validation_reference="synthetic-fixture-only",
    )
    return LongPosition.model_validate(
        {
            "episode_id": UUID(int=20 + list(Asset).index(asset)),
            "asset": asset,
            "instrument_id": asset.value,
            "quantity": "2",
            "quantity_unit": "lot",
            "price_unit": "USD-price-point",
            "weighted_actual_entry": "100.5",
            "current_bid": "102.5",
            "quote_id": "quote-fixture",
            "quote_at": T,
            "reconciled_sequence": 0,
            "valuation_model": model,
            **updates,
        }
    )


def cash_change(amount: str, category: Category = Category.REALIZED_PNL) -> AccountInput:
    e = entry(amount, category)
    return account(e.effective_at, ledger=(e,))


def test_empty_account_authoritative_fields() -> None:
    result = project_portfolio((account(),))
    snapshot = result.equity_snapshot
    assert snapshot.equity == snapshot.balance.cash_balance == 1000
    assert snapshot.unrealized_pnl == snapshot.balance.realized_pnl == 0
    assert snapshot.complete and not snapshot.stale and result.accounting_entry_eligible
    assert snapshot.open_episode_count == snapshot.reserved_episode_count == 0
    assert snapshot.source.used_margin is None and snapshot.source.open_stop_risk is None
    assert tuple(a.asset.value for a in snapshot.assets) == ("BTCUSD", "USTEC100", "XAUUSD")
    assert result.nav.nav == result.nav.high_water_mark == 1
    assert result.risk_day.today_trading_pnl == result.nav.drawdown == 0
    assert not result.qualification_eligible


@pytest.mark.parametrize("bid,pnl", [("102.5", "40"), ("98.5", "-40"), ("100.5", "0")])
def test_bid_mark_with_explicit_factor_and_actual_entry(bid: str, pnl: str) -> None:
    result = project_equity(account(positions=(position(current_bid=bid),)))
    assert result.unrealized_pnl == D(pnl)
    assert result.equity == 1000 + D(pnl)
    assert result.assets[0].position is not None
    assert result.assets[0].position.weighted_actual_entry == D("100.5")


def test_three_positions_different_contract_factors_and_partial_quantity() -> None:
    positions = []
    for asset, quantity, factor in [
        (Asset.BTCUSD, "0.25", "1"),
        (Asset.USTEC100, "2", "20"),
        (Asset.XAUUSD, "0.5", "100"),
    ]:
        p = position(asset, quantity=quantity)
        assert p.valuation_model is not None
        positions.append(
            p.model_copy(
                update={
                    "valuation_model": p.valuation_model.model_copy(
                        update={
                            "usd_per_quantity_price_unit": factor,
                        }
                    ),
                }
            )
        )
    result = project_equity(account(positions=tuple(positions)))
    assert result.unrealized_pnl == D("180.5")  # 0.5 + 80 + 100
    assert result.equity == D("1180.5") and result.open_episode_count == 3


def test_separate_categories_and_audited_reversal_replacement() -> None:
    values = [
        ("100", Category.CASH_FLOW),
        ("20", Category.REALIZED_PNL),
        ("-2", Category.COMMISSION),
        ("-3", Category.FINANCING),
        ("1", Category.FINANCING),
        ("5", Category.ADJUSTMENT),
    ]
    ledger = tuple(
        entry(v, c, i, audit_reference="audit-fixture") for i, (v, c) in enumerate(values, 1)
    )
    original = ledger[1]
    reversal = entry("-20", sequence=7, reverses=original.entry_id, audit_reference="correction")
    replacement = entry("12", sequence=8, replaces=original.entry_id, audit_reference="correction")
    result = project_balance(
        account(T + timedelta(hours=1), ledger=(*ledger, reversal, replacement))
    )
    assert result.external_cash_flows == 100
    assert result.realized_pnl == 12 and result.commissions == -2
    assert result.financing == -2 and result.audited_adjustments == 5
    assert result.cash_balance == 1113
    assert original.amount == 20


@pytest.mark.parametrize("amount", ["100", "-100", "25.75", "-0.5"])
def test_flows_do_not_change_nav_or_daily_trading_pnl(amount: str) -> None:
    at = T + timedelta(hours=1)
    pre = account(at)
    flow = entry(amount, Category.CASH_FLOW, at=at)
    post = account(at, ledger=(flow,))
    result = project_portfolio((account(), pre, post))
    assert result.nav.nav == result.nav.high_water_mark == 1
    assert result.nav.drawdown == result.risk_day.today_trading_pnl == 0
    assert result.nav.units == 1000 + D(amount)
    assert result.risk_day.net_external_flows == D(amount)


def test_unitized_deposit_after_profit_preserves_high_water_mark() -> None:
    profit = entry("100")
    pre = account(profit.effective_at, ledger=(profit,))
    flow = entry("550", Category.CASH_FLOW, 2, at=profit.effective_at)
    post = account(flow.effective_at, ledger=(profit, flow))
    loss = entry("-82.5", sequence=3, at=T + timedelta(hours=2))
    end = account(loss.effective_at, ledger=(profit, flow, loss))
    result = project_portfolio((account(), pre, post, end))
    assert result.nav.units == 1500
    assert result.nav.high_water_mark == D("1.1")
    assert result.nav.nav == D("1.045")
    assert result.nav.drawdown == D("0.05") and result.nav.drawdown_triggered
    assert result.risk_day.today_trading_pnl == D("17.5")


@pytest.mark.parametrize("loss,triggered", [("-49.999", False), ("-50", True), ("-50.001", True)])
def test_drawdown_threshold(loss: str, triggered: bool) -> None:
    result = project_portfolio((account(), cash_change(loss)))
    assert result.nav.drawdown_triggered is triggered


@pytest.mark.parametrize("loss,triggered", [("-14.999", False), ("-15", True), ("-15.001", True)])
def test_daily_threshold(loss: str, triggered: bool) -> None:
    result = project_portfolio((account(), cash_change(loss)))
    assert result.risk_day.daily_loss_triggered is triggered
    assert result.accounting_entry_eligible is (not triggered)


def test_daily_utc_rollover_and_bangkok_midnight() -> None:
    bangkok = T.replace(hour=17).astimezone(timezone(timedelta(hours=7)))
    assert bangkok.hour == 0 and bangkok.day == 15
    e = entry("-15", at=T + timedelta(hours=1))
    same_day = account(bangkok, ledger=(e,))
    result = project_portfolio((account(), same_day))
    assert result.risk_day.boundary_at == T and result.risk_day.daily_loss_triggered
    midnight = account(T + timedelta(days=1), ledger=(e,))
    result = project_portfolio((account(), same_day, midnight))
    assert result.risk_day.boundary_equity == 985
    assert result.risk_day.today_trading_pnl == 0
    assert not result.risk_day.daily_loss_triggered
    assert result.nav.high_water_mark == 1
    assert result.nav.drawdown == D("0.015")


def test_missing_boundary_is_not_zero_daily_loss() -> None:
    result = project_portfolio((account(), account(T + timedelta(days=1, hours=1))))
    assert result.risk_day.daily_loss_fraction is None
    assert result.risk_day.unavailable_reason == "MISSING_VALID_UTC_MIDNIGHT_VALUATION"
    assert not result.accounting_entry_eligible


@pytest.mark.parametrize("seconds,stale", [(5, False), (6, True)])
def test_quote_staleness(seconds: int, stale: bool) -> None:
    result = project_equity(account(T + timedelta(seconds=seconds), positions=(position(),)))
    assert result.stale is stale
    assert result.equity == 1040 and result.complete
    if stale:
        full = project_portfolio((account(positions=(position(),)), result.source))
        assert not full.accounting_entry_eligible and full.nav.nav is None


@pytest.mark.parametrize("seconds,stale", [(15, False), (16, True)])
def test_account_staleness(seconds: int, stale: bool) -> None:
    result = project_equity(account(T + timedelta(seconds=seconds), reconciled_at=T))
    assert result.stale is stale


@pytest.mark.parametrize(
    "kind", ["missing", "unvalidated", "mismatch", "expired", "units", "quote"]
)
def test_unavailable_model_or_quote_propagates_unknown_equity(kind: str) -> None:
    p = position()
    assert p.valuation_model is not None
    if kind == "missing":
        p = p.model_copy(update={"valuation_model": None})
    elif kind == "quote":
        p = p.model_copy(update={"current_bid": None, "quote_id": None, "quote_at": None})
    else:
        changes: dict[str, dict[str, Any]] = {
            "unvalidated": {"validation_reference": None},
            "mismatch": {"asset": Asset.XAUUSD},
            "expired": {"valid_until": T},
            "units": {"quantity_unit": "other-unit"},
        }
        assert p.valuation_model is not None
        p = p.model_copy(
            update={"valuation_model": p.valuation_model.model_copy(update=changes[kind])}
        )
    result = project_portfolio((account(positions=(p,)),))
    assert result.equity_snapshot.equity is None
    assert result.equity_snapshot.unrealized_pnl is None
    assert not result.equity_snapshot.complete and not result.accounting_entry_eligible
    assert result.equity_snapshot.assets[0].unavailable_reason


def test_risk_margin_and_occupancy_are_supplied_not_sized() -> None:
    source = account(
        positions=(position(),),
        reservations=(Reservation(episode_id=UUID(int=50), asset=Asset.XAUUSD),),
        used_margin="10",
        reserved_margin="2",
        open_stop_risk="3",
        reserved_stop_risk="1",
    )
    result = project_equity(source)
    assert result.source.used_margin == 10 and result.source.reserved_margin == 2
    assert result.source.open_stop_risk == 3 and result.source.reserved_stop_risk == 1
    assert result.open_episode_count == result.reserved_episode_count == 1
    assert result.assets[2].reserved_episode == UUID(int=50)
    with pytest.raises(ValidationError, match="ONE_OPEN_OR_PENDING"):
        source.model_copy(
            update={"reservations": (Reservation(episode_id=UUID(int=50), asset=Asset.BTCUSD),)}
        )


@pytest.mark.parametrize(
    "field",
    ["opening_cash", "used_margin", "reserved_margin", "open_stop_risk", "reserved_stop_risk"],
)
def test_account_floats_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        account().model_copy(update={field: 1.0})


@pytest.mark.parametrize("field", ["quantity", "weighted_actual_entry", "current_bid"])
def test_position_floats_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        position().model_copy(update={field: 1.0})


@pytest.mark.parametrize("amount", [1.0, True, "NaN", "Infinity", "bad", "1e101"])
def test_ledger_malformed_decimal_rejected(amount: object) -> None:
    with pytest.raises(ValidationError):
        entry().model_copy(update={"amount": amount})


@pytest.mark.parametrize("field", ["valuation_at", "reconciled_at", "opening_at"])
def test_naive_account_time_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        account(**{field: T.replace(tzinfo=None)})


def test_other_naive_times_currency_direction_and_model_float_rejected() -> None:
    for field in ("effective_at", "recorded_at"):
        with pytest.raises(ValidationError):
            entry().model_copy(update={field: T.replace(tzinfo=None)})
    for changes in ({"quote_at": T.replace(tzinfo=None)}, {"direction": "SHORT"}):
        with pytest.raises(ValidationError):
            position(**changes)
    for currency in ("EUR", "usd"):
        with pytest.raises(ValidationError):
            account(currency=currency)
        with pytest.raises(ValidationError):
            entry(currency=currency)
    model = position().valuation_model
    assert model is not None
    for model_changes in (
        {"usd_per_quantity_price_unit": 1.0},
        {"valid_from": T.replace(tzinfo=None)},
    ):
        with pytest.raises(ValidationError):
            model.model_copy(update=model_changes)


def test_ledger_duplicate_order_account_and_correction_rejections() -> None:
    original = entry()
    cases = [
        (original, original),
        (original.model_copy(update={"sequence": 2}),),
        (original.model_copy(update={"account_id": UUID(int=2)}),),
        (original, entry("-9", sequence=2, reverses=original.entry_id, audit_reference="audit")),
        (original, entry("9", sequence=2, replaces=original.entry_id, audit_reference="audit")),
        (original, entry(sequence=2, at=T)),
    ]
    for ledger in cases:
        with pytest.raises(ValidationError):
            account(T + timedelta(hours=1), ledger=ledger)
    with pytest.raises(ValidationError, match="AUDIT"):
        entry(category=Category.ADJUSTMENT)


def test_immutable_and_validated_copy() -> None:
    source = account()
    with pytest.raises(ValidationError):
        source.opening_cash = D(2)  # type: ignore[misc]  # Exercise runtime immutability.
    with pytest.raises(ValidationError):
        source.model_copy(update={"opening_cash": 1.0})
    with pytest.raises(TypeError, match="UNCHECKED"):
        AccountInput.model_construct(**source.model_dump())


def test_context_contamination_and_scale_identity() -> None:
    inputs = (account(), cash_change("-12.345678901234567890123456789"))
    expected = project_portfolio(inputs)
    with localcontext() as ctx:
        ctx.prec = 3
        ctx.rounding = ROUND_DOWN
        ctx.traps[Inexact] = True
        actual = project_portfolio(inputs)
    assert expected == actual and expected.identity == actual.identity
    scaled = account(opening_cash="1000.0000")
    assert scaled.identity == account().identity
    assert project_portfolio((scaled,)).identity == project_portfolio((account(),)).identity


@pytest.mark.parametrize("kind", ["no_pre", "netted", "wrong_post", "withdraw_all"])
def test_invalid_flow_history_unavailable(kind: str) -> None:
    at = T + timedelta(hours=1)
    flow = entry("-1000" if kind == "withdraw_all" else "100", Category.CASH_FLOW, at=at)
    ledger: tuple[LedgerEntry, ...] = (flow,)
    if kind == "netted":
        ledger += (entry("-50", Category.CASH_FLOW, 2, at=at),)
    if kind == "wrong_post":
        ledger += (entry("5", sequence=2, at=at),)
    history = (account(),) if kind == "no_pre" else (account(), account(at))
    result = project_portfolio((*history, account(at, ledger=ledger)))
    assert result.nav.nav is None and result.nav.unavailable_reason
    assert not result.accounting_entry_eligible


def test_forged_or_reordered_history_rejected() -> None:
    a = cash_change("10")
    for inputs in (
        (a, account()),
        (account(), account()),
        (account(), account(T + timedelta(hours=1), opening_cash="2000")),
        (a, cash_change("11")),
    ):
        with pytest.raises(ValueError):
            project_portfolio(inputs)


def test_midnight_flow_uses_pre_flow_boundary_and_missing_pre_is_unavailable() -> None:
    at = T + timedelta(days=1)
    flow = entry("500", Category.CASH_FLOW, at=at)
    pre, post = account(at), account(at, ledger=(flow,))
    result = project_portfolio((account(), pre, post))
    assert result.risk_day.boundary_equity == 1000
    assert result.risk_day.net_external_flows == 500
    assert result.risk_day.today_trading_pnl == 0
    missing = project_portfolio((account(), post))
    assert missing.risk_day.unavailable_reason == "MISSING_PRE_FLOW_UTC_MIDNIGHT_VALUATION"
    assert missing.nav.unavailable_reason and not missing.accounting_entry_eligible


def test_multiple_separate_flows_and_recovery_preserve_nav_history() -> None:
    at = T + timedelta(hours=1)
    loss = entry("-50", at=at)
    pre = account(at, ledger=(loss,))
    withdrawal = entry("-475", Category.CASH_FLOW, 2, at=at)
    post = account(at, ledger=(loss, withdrawal))
    result = project_portfolio((account(), pre, post))
    assert result.nav.units == 500 and result.nav.nav == D("0.95")
    assert result.nav.high_water_mark == 1 and result.nav.drawdown_triggered
    deposit = entry("95", Category.CASH_FLOW, 3, at=at)
    deposited = account(at, ledger=(loss, withdrawal, deposit))
    recovery = entry("30", sequence=4, at=T + timedelta(hours=2))
    end = account(recovery.effective_at, ledger=(loss, withdrawal, deposit, recovery))
    result = project_portfolio((account(), pre, post, deposited, end))
    assert result.nav.units == 600 and result.nav.nav == 1
    assert result.nav.high_water_mark == 1 and result.nav.drawdown == 0
    assert result.risk_day.today_trading_pnl == -20


def test_unknown_inception_does_not_invent_high_water_mark() -> None:
    for source in (account(opening_cash="0"), account(T + timedelta(hours=1))):
        result = project_portfolio((source,))
        assert result.nav.high_water_mark is None and result.nav.nav is None
        assert not result.accounting_entry_eligible


def test_stale_history_remains_incomplete_until_reconstructed() -> None:
    stale = account(T + timedelta(seconds=16), reconciled_at=T)
    fresh = account(T + timedelta(seconds=17))
    result = project_portfolio((account(), stale, fresh))
    assert result.nav.high_water_mark == 1 and result.nav.nav is None
    assert not result.accounting_entry_eligible
    reconstructed = stale.model_copy(update={"reconciled_at": stale.valuation_at})
    assert project_portfolio((account(), reconstructed, fresh)).accounting_entry_eligible


def test_changed_reconciled_partial_fill_and_costs() -> None:
    p = position(quantity="0.5", weighted_actual_entry="100.015", current_bid="101.015")
    initial = account(positions=(p,))
    fee = entry("-2", Category.COMMISSION, at=T + timedelta(seconds=1))
    partial = p.model_copy(
        update={
            "quantity": "0.75",
            "weighted_actual_entry": "100.115",
            "reconciled_sequence": 1,
            "quote_at": fee.effective_at,
            "quote_id": "next-quote",
        }
    )
    end = account(fee.effective_at, ledger=(fee,), positions=(partial,))
    result = project_portfolio((initial, end))
    assert result.equity_snapshot.unrealized_pnl == D("6.75")
    assert result.equity_snapshot.balance.commissions == -2
    assert result.equity_snapshot.equity == D("1004.75")
    assert result.risk_day.today_trading_pnl == D("-0.25")


def test_correction_cannot_repeat_reverse_or_replace() -> None:
    original = entry()
    reversal = entry("-10", sequence=2, reverses=original.entry_id, audit_reference="audit")
    replacement = entry("9", sequence=3, replaces=original.entry_id, audit_reference="audit")
    for next_entry in (
        entry("-10", sequence=4, reverses=original.entry_id, audit_reference="audit"),
        entry("8", sequence=4, replaces=original.entry_id, audit_reference="audit"),
    ):
        with pytest.raises(ValidationError):
            account(T + timedelta(hours=1), ledger=(original, reversal, replacement, next_entry))


def test_exact_comparison_does_not_round_near_threshold_into_breach() -> None:
    # Both are within the 34-significant-digit boundary; compare cross products
    # exactly, without first rounding a percentage to display precision.
    result = project_portfolio((account(), cash_change("-49.9999999999999999999999999999")))
    assert result.nav.drawdown_triggered is False
    daily = project_portfolio((account(), cash_change("-14.9999999999999999999999999999")))
    assert daily.risk_day.daily_loss_triggered is False


@settings(max_examples=75, derandomize=True)
@given(st.integers(min_value=-99900, max_value=1000000))
def test_property_cash_flow_neutrality(cents: int) -> None:
    amount = D(cents) / 100
    at = T + timedelta(hours=1)
    post = account(at, ledger=(entry(str(amount), Category.CASH_FLOW, at=at),))
    result = project_portfolio((account(), account(at), post))
    assert result.nav.nav == 1 and result.nav.drawdown == 0
    assert result.risk_day.today_trading_pnl == 0
    assert result.equity_snapshot.equity == 1000 + amount


@settings(max_examples=75, derandomize=True)
@given(st.integers(-10000, 10000), st.integers(-10000, 10000))
def test_property_ledger_component_conservation(realized: int, financing: int) -> None:
    ledger = (entry(str(realized)), entry(str(financing), Category.FINANCING, 2))
    result = project_equity(account(T + timedelta(hours=1), ledger=ledger))
    assert result.equity == 1000 + realized + financing
    assert result.balance.realized_pnl == realized and result.balance.financing == financing
