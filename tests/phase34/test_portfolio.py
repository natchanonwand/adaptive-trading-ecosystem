from datetime import timedelta
from decimal import Inexact, localcontext
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from tests.phase34.fixtures import D, T, book, economics, fill, quote
from trading_ecosystem.portfolio.contracts import Observation
from trading_ecosystem.portfolio.fills import apply_fill
from trading_ecosystem.portfolio.projection import project


@pytest.mark.parametrize(
    "direction,side,expected", [("LONG", "BUY", "-0.20"), ("SHORT", "SELL", "0")]
)
def test_bid_ask_marks(direction: str, side: str, expected: str) -> None:
    initial = book()
    filled = apply_fill(initial, fill(direction=direction, side=side))
    result = project((Observation(book=initial), Observation(book=filled, quotes=(quote(),))))
    assert result.accounting.unrealized_pnl == D(expected)
    assert result.accounting.equity == D("10000") + D(expected)
    assert result.used_margin == 1
    assert result.free_margin == result.accounting.equity - 1


@pytest.mark.parametrize(
    "direction,entry_side,exit_side,expected",
    [
        ("LONG", "BUY", "SELL", "4"),
        ("SHORT", "SELL", "BUY", "-4"),
    ],
)
def test_partial_and_full_close(
    direction: str, entry_side: str, exit_side: str, expected: str
) -> None:
    initial = apply_fill(book(), fill(direction=direction, side=entry_side))
    partial = apply_fill(
        initial,
        fill(
            2,
            action="REDUCE",
            side=exit_side,
            direction=direction,
            quantity="0.04",
            actual_price="101",
            actual_commission="-0.2",
        ),
    )
    assert partial.positions[0].quantity == D("0.06")
    assert partial.positions[0].direction == direction
    full = apply_fill(
        partial,
        fill(
            3,
            action="REDUCE",
            side=exit_side,
            direction=direction,
            quantity="0.06",
            actual_price="101",
        ),
    )
    assert full.positions == ()
    snap = project((Observation(book=book()), Observation(book=full)))
    assert snap.accounting.balance.realized_pnl == D(expected) * D("2.5")
    assert snap.accounting.balance.commissions == D("-0.2")
    assert snap.accounting.unrealized_pnl == 0


def test_weighted_entry_multiple_fills_and_no_entry_after_reduction() -> None:
    first = apply_fill(book(), fill(quantity="0.1", actual_price="100"))
    second = apply_fill(first, fill(2, quantity="0.2", actual_price="103"))
    assert second.positions[0].weighted_entry == 102 and second.positions[0].quantity == D("0.3")
    reduced = apply_fill(second, fill(3, quantity="0.1", action="REDUCE", side="SELL"))
    with pytest.raises(ValueError, match="ENTRY_AFTER_REDUCTION"):
        apply_fill(reduced, fill(4))


def test_oversized_exit_duplicate_fill_and_conflict() -> None:
    f = fill()
    initial = apply_fill(book(), f)
    assert apply_fill(initial, f) == initial
    with pytest.raises(ValueError, match="CONFLICTING_DUPLICATE"):
        apply_fill(initial, f.model_copy(update={"quantity": "0.2"}))
    with pytest.raises(ValueError, match="REVERSE"):
        apply_fill(initial, fill(2, action="REDUCE", side="SELL", quantity="0.11"))


def test_multiple_assets_and_strategy_attribution() -> None:
    first = apply_fill(book(), fill())
    e = economics(asset="XAUUSD", instrument_id="fixture-XAU")
    second = apply_fill(
        first,
        fill(2, asset="XAUUSD", economics=e, strategy_id=UUID(int=88), episode_id=UUID(int=89)),
    )
    current = Observation(
        book=second,
        quotes=(quote(), quote(instrument_id="fixture-XAU", at=second.cash.valuation_at)),
    )
    result = project((Observation(book=book()), current))
    assert len(result.marks) == 2 and result.accounting.open_episode_count == 2
    assert result.accounting.unrealized_pnl == D("-0.4")
    assert len({p.strategy_id for p in result.source.book.positions}) == 2


def test_missing_valuation_unknown_and_stale_mark_label() -> None:
    filled = apply_fill(book(), fill())
    result = project((Observation(book=book()), Observation(book=filled)))
    assert result.accounting.equity is None and result.open_risk is None
    later = filled.model_copy(
        update={
            "cash": filled.cash.model_copy(
                update={
                    "valuation_at": T + timedelta(seconds=7),
                    "reconciled_at": T + timedelta(seconds=7),
                }
            )
        }
    )
    result = project((Observation(book=book()), Observation(book=later, quotes=(quote(),))))
    assert result.accounting.stale and result.accounting.equity is not None
    assert result.nav.unavailable_reason


@pytest.mark.parametrize("field", ["quantity", "actual_price", "actual_commission", "fixed_stop"])
def test_fill_float_rejection(field: str) -> None:
    with pytest.raises(ValidationError):
        fill().model_copy(update={field: 0.1})


def test_context_and_scale_determinism() -> None:
    expected = apply_fill(book(), fill())
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.traps[Inexact] = True
        actual = apply_fill(book(), fill(quantity="0.10000"))
    assert actual.identity == expected.identity


@settings(max_examples=60, derandomize=True)
@given(st.integers(1, 99))
def test_partial_quantity_conservation(units: int) -> None:
    first = apply_fill(book(), fill(quantity="1"))
    reduction = D(units) / 100
    reduced = apply_fill(first, fill(2, action="REDUCE", side="SELL", quantity=str(reduction)))
    assert reduced.positions[0].quantity + reduction == 1
