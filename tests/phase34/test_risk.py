from datetime import timedelta
from decimal import Inexact, localcontext
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from tests.phase34.fixtures import D, T, book, economics, quote, request
from trading_ecosystem.accounting.contracts import Category, LedgerEntry
from trading_ecosystem.portfolio.contracts import Observation, Reservation
from trading_ecosystem.risk.contracts import Health, Policy
from trading_ecosystem.risk.engine import evaluate, evaluate_and_reserve


def test_v0_sizing_and_risk_owned_volume() -> None:
    r = request()
    result = evaluate(r)
    assert result.accepted and result.order is not None
    assert result.order.volume == D("0.24")  # 25 / (100 * 1.02), rounded down
    assert result.order.estimated_stop_risk == D("24.48")
    assert result.order.fixed_stop == r.intent.fixed_stop
    with pytest.raises(ValidationError):
        r.intent.model_copy(update={"volume": "100"})


def test_minimum_lot_risk_102_exceeds_075_budget() -> None:
    a = book(opening_cash="300")
    b = book(
        opening_cash="300",
        valuation_at=T + timedelta(seconds=1),
        reconciled_at=T + timedelta(seconds=1),
    )
    result = evaluate(request(history=(Observation(book=a), Observation(book=b))))
    assert not result.accepted and "NEW_EPISODE_RISK_LIMIT" in result.reasons
    assert result.order is None


def test_hr_five_percent_and_short_isolated() -> None:
    r = request(policy=Policy(policy_id="HR_DEMO_5PCT"))
    result = evaluate(r)
    assert result.order is not None and result.order.volume == D("4.90")
    assert result.order.estimated_stop_risk == D("499.80")
    short = r.model_copy(
        update={"intent": r.intent.model_copy(update={"direction": "SHORT", "fixed_stop": "101"})}
    )
    assert evaluate(short).accepted
    conservative = short.model_copy(update={"policy": Policy()})
    assert "V0_LONG_ONLY" in evaluate(conservative).reasons


@pytest.mark.parametrize("mode", ["RESEARCH", "DEMO_OPERATIONAL"])
def test_hr_forbidden_modes(mode: str) -> None:
    result = evaluate(request(mode=mode, policy=Policy(policy_id="HR_DEMO_5PCT")))
    assert not result.accepted and "EXPERIMENTAL_MODE_FORBIDDEN" in result.reasons


@pytest.mark.parametrize("kind", ["REAL", "UNKNOWN"])
@pytest.mark.parametrize("policy", ["V0_CONSERVATIVE", "HR_DEMO_5PCT"])
def test_real_and_unknown_accounts_rejected(kind: str, policy: str) -> None:
    r = request(policy=Policy.model_validate({"policy_id": policy}))
    result = evaluate(
        r.model_copy(update={"health": r.health.model_copy(update={"account_kind": kind})})
    )
    assert not result.accepted and "ACCOUNT_TYPE_REJECTED" in result.reasons


def test_hr_seven_percent_existing_plus_five_rejected() -> None:
    r = request(policy=Policy(policy_id="HR_DEMO_5PCT"))
    reserve = Reservation(
        reservation_id="existing",
        intent_id=UUID(int=50),
        strategy_id=UUID(int=51),
        asset="XAUUSD",
        direction="LONG",
        volume=D("1"),
        stop_risk=D("700"),
        margin=D("1"),
        gross_notional=D("100"),
        decision_id="prior",
    )
    current = r.history[-1].model_copy(update={"reservations": (reserve,)})
    result = evaluate(r.model_copy(update={"history": (*r.history[:-1], current)}))
    assert not result.accepted and result.reasons == ("AGGREGATE_RISK_LIMIT",)


def test_serial_reservation_blocks_duplicate_asset() -> None:
    r = request()
    first, history = evaluate_and_reserve(r)
    assert first.accepted and len(history[-1].reservations) == 1
    second, unchanged = evaluate_and_reserve(r.model_copy(update={"history": history}))
    assert not second.accepted and "ASSET_OCCUPIED" in second.reasons
    assert unchanged == history


@pytest.mark.parametrize(
    "changes,volume",
    [
        ({"volume_max": "0.10"}, "0.10"),
        ({"volume_min": "0.015", "volume_step": "0.02"}, "0.235"),
        ({"volume_min": "0.01", "volume_step": "0.1"}, "0.21"),
    ],
)
def test_volume_lattice(changes: dict[str, str], volume: str) -> None:
    result = evaluate(request(economics=economics(**changes)))
    assert result.order is not None and result.order.volume == D(volume)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("margin_per_lot", "300000", "MARGIN_LIMIT"),
        ("contract_size", "30000", "GROSS_NOTIONAL_LIMIT"),
    ],
)
def test_minimum_margin_exposure_rejected(field: str, value: str, reason: str) -> None:
    result = evaluate(request(economics=economics(**{field: value})))
    assert reason in result.reasons and not result.accepted


def test_v0_largest_feasible_margin_constrained_volume() -> None:
    result = evaluate(request(economics=economics(margin_per_lot="10000")))
    assert result.order is not None and result.order.volume == D("0.20")


@pytest.mark.parametrize(
    "field",
    [
        "broker_connected",
        "reconciled",
        "lease_valid",
        "approval_valid",
        "session_open",
        "calendar_validated",
        "protection_confirmed",
    ],
)
def test_health_fail_closed(field: str) -> None:
    r = request()
    result = evaluate(r.model_copy(update={"health": r.health.model_copy(update={field: False})}))
    assert not result.accepted and result.state.status == "PAUSE_ENTRIES"


def test_unknown_submission_and_default_health_reject() -> None:
    r = request()
    for health in (Health(), r.health.model_copy(update={"unknown_submission": True})):
        assert not evaluate(r.model_copy(update={"health": health})).accepted


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"quote": None}, "STALE_OR_MISSING_QUOTE"),
        ({"economics": None}, "MISSING_VALIDATED_ECONOMICS"),
        ({"quote": quote(at=T - timedelta(seconds=5))}, "STALE_OR_MISSING_QUOTE"),
        ({"quote": quote(bid="99.8")}, "SPREAD_LIMIT"),
        ({"economics": economics(validation_reference=None)}, "MISSING_VALIDATED_ECONOMICS"),
    ],
)
def test_unknown_and_bad_inputs(change: dict[str, object], reason: str) -> None:
    result = evaluate(request(**change))
    assert not result.accepted and reason in result.reasons


@pytest.mark.parametrize(
    "policy,loss,halt",
    [
        ("V0_CONSERVATIVE", "-149.99", False),
        ("V0_CONSERVATIVE", "-150", True),
        ("HR_DEMO_5PCT", "-999.99", False),
        ("HR_DEMO_5PCT", "-1000", True),
    ],
)
def test_policy_daily_thresholds(policy: str, loss: str, halt: bool) -> None:
    r = request(policy=Policy.model_validate({"policy_id": policy}))
    cash = r.history[-1].book.cash
    posting = LedgerEntry(
        entry_id=UUID(int=900),
        account_id=cash.account_id,
        sequence=1,
        amount=D(loss),
        category=Category.REALIZED_PNL,
        reference_id=UUID(int=901),
        effective_at=r.at,
        recorded_at=r.at,
    )
    current = Observation(
        book=book().model_copy(update={"cash": cash.model_copy(update={"ledger": (posting,)})})
    )
    result = evaluate(r.model_copy(update={"history": (r.history[0], current)}))
    assert (result.state.status == "HALT_AND_FLATTEN") is halt


def test_halt_latched_on_recovery_and_policy_switch_rejected() -> None:
    r = request()
    severe = evaluate(
        r.model_copy(update={"health": r.health.model_copy(update={"severe_breach": True})})
    )
    recovered = evaluate(r.model_copy(update={"prior_state": severe.state}))
    assert recovered.state.status == "HALT_AND_FLATTEN" and not recovered.accepted
    with pytest.raises(ValueError, match="PRIOR_RISK_STATE"):
        evaluate(
            r.model_copy(
                update={"prior_state": severe.state, "policy": Policy(policy_id="HR_DEMO_5PCT")}
            )
        )


def test_missing_midnight_stale_account_and_future_quote() -> None:
    r = request()
    for change in (
        {"history": (r.history[-1],)},
        {"at": T + timedelta(seconds=17), "quote": quote(at=T + timedelta(seconds=17))},
        {"quote": quote(at=T + timedelta(seconds=2))},
    ):
        assert not evaluate(r.model_copy(update=change)).accepted


def test_known_commissions_reduce_size_without_double_spread_charge() -> None:
    result = evaluate(
        request(
            economics=economics(commission_per_lot_per_side="1", commission_fixed_per_side="0.1")
        )
    )
    assert result.order is not None and result.order.volume == D("0.23")
    assert result.order.estimated_stop_risk == D("24.12")  # .23*(102+2)+.2


@pytest.mark.parametrize(
    "field",
    [
        "tick_size",
        "tick_value_per_lot",
        "contract_size",
        "usd_per_price_unit_per_lot",
        "volume_min",
        "volume_max",
        "volume_step",
        "margin_per_lot",
        "commission_per_lot_per_side",
        "commission_fixed_per_side",
    ],
)
def test_economics_rejects_float(field: str) -> None:
    with pytest.raises(ValidationError):
        economics().model_copy(update={field: 1.0})


def test_intent_naive_time_and_unpinned_policy_reject() -> None:
    with pytest.raises(ValidationError):
        request().intent.model_copy(update={"signal_at": T.replace(tzinfo=None)})
    with pytest.raises(ValidationError):
        Policy.model_validate({"risk_per_trade": "0.05"})


def test_extreme_magnitude_cannot_round_off_broker_lattice() -> None:
    r = request(economics=economics(volume_step="0.02", volume_max="1e34"))
    history = tuple(
        o.model_copy(
            update={
                "book": o.book.model_copy(
                    update={"cash": o.book.cash.model_copy(update={"opening_cash": "1e38"})}
                )
            }
        )
        for o in r.history
    )
    result = evaluate(r.model_copy(update={"history": history}))
    assert not result.accepted
    assert "VOLUME_LATTICE_EXCEEDS_DECIMAL_PRECISION" in result.reasons


def test_caller_context_and_equivalent_scale_identity() -> None:
    original = request()
    expected = evaluate(original)
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.traps[Inexact] = True
        actual = evaluate(
            original.model_copy(update={"economics": economics(volume_step="0.01000")})
        )
    assert actual.identity == expected.identity


@pytest.mark.parametrize(
    "policy,loss,dd",
    [
        ("V0_CONSERVATIVE", "-499.99", False),
        ("V0_CONSERVATIVE", "-500", True),
        ("V0_CONSERVATIVE", "-500.01", True),
        ("HR_DEMO_5PCT", "-2999.99", False),
        ("HR_DEMO_5PCT", "-3000", True),
        ("HR_DEMO_5PCT", "-3000.01", True),
    ],
)
def test_drawdown_thresholds_and_midnight_cannot_erase_daily_halt(
    policy: str, loss: str, dd: bool
) -> None:
    r = request(policy=Policy.model_validate({"policy_id": policy}))
    midnight = T + timedelta(days=1)
    cash = book(valuation_at=midnight, reconciled_at=midnight).cash
    posting = LedgerEntry(
        entry_id=UUID(int=950),
        account_id=cash.account_id,
        sequence=1,
        amount=D(loss),
        category=Category.REALIZED_PNL,
        reference_id=UUID(int=951),
        effective_at=midnight,
        recorded_at=midnight,
    )
    current = Observation(
        book=book().model_copy(update={"cash": cash.model_copy(update={"ledger": (posting,)})})
    )
    result = evaluate(
        r.model_copy(
            update={"history": (r.history[0], current), "at": midnight, "quote": quote(at=midnight)}
        )
    )
    assert ("DRAWDOWN_HALT" in result.reasons) is dd
    assert "DAILY_LOSS_HALT_AT_ROLLOVER" in result.reasons


def test_supplied_used_margin_cannot_be_ignored() -> None:
    r = request()
    current = r.history[-1]
    current = current.model_copy(
        update={
            "book": current.book.model_copy(
                update={"cash": current.book.cash.model_copy(update={"used_margin": "2000"})}
            )
        }
    )
    result = evaluate(r.model_copy(update={"history": (r.history[0], current)}))
    assert "MARGIN_LIMIT" in result.reasons


def test_position_count_limit_and_distinct_symbol_reservations() -> None:
    r = request(policy=Policy(policy_id="HR_DEMO_5PCT"))
    reserves = tuple(
        Reservation(
            reservation_id=str(i),
            intent_id=UUID(int=60 + i),
            strategy_id=UUID(int=70 + i),
            asset=asset,
            direction="LONG",
            volume=D("0.01"),
            stop_risk=D("1"),
            gross_notional=D("1"),
            margin=D("1"),
            decision_id="fixture",
        )
        for i, asset in enumerate(("XAUUSD", "USTEC100"))
    )
    current = r.history[-1].model_copy(update={"reservations": reserves})
    assert (
        "POSITION_COUNT_LIMIT"
        in evaluate(r.model_copy(update={"history": (r.history[0], current)})).reasons
    )


@settings(max_examples=60, derandomize=True)
@given(st.integers(100, 100000))
def test_property_sizing_never_exceeds_budget_or_lattice(cash_amount: int) -> None:
    r = request()
    history = tuple(
        o.model_copy(
            update={
                "book": o.book.model_copy(
                    update={
                        "cash": o.book.cash.model_copy(update={"opening_cash": str(cash_amount)})
                    }
                )
            }
        )
        for o in r.history
    )
    result = evaluate(r.model_copy(update={"history": history}))
    if result.order:
        assert result.order.estimated_stop_risk <= D(cash_amount) * D("0.0025")
        assert result.order.volume >= D("0.01")
        assert result.order.volume % D("0.01") == 0
        assert result.order.estimated_stop_risk + D("1.02") > D(cash_amount) * D("0.0025")
