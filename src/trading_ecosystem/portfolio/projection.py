"""Bid/ask valuation and reuse of Phase 3.4A NAV/day arithmetic kernels."""

from datetime import timedelta
from decimal import Decimal
from typing import Literal

from trading_ecosystem.accounting.contracts import Contract, EquitySnapshot, NavState, RiskDayState
from trading_ecosystem.accounting.performance import _day, _nav
from trading_ecosystem.accounting.projection import project_balance
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import EntityId, Money
from trading_ecosystem.portfolio.contracts import Observation

ZERO = Decimal(0)


class Mark(Contract):
    episode_id: EntityId
    unrealized_pnl: Money | None
    stop_risk: Money | None
    gross_notional: Money | None
    margin: Money | None
    unavailable_reason: str | None
    stale: bool


class ValuationPoint(EquitySnapshot):
    """Aggregate cash/valuation bridge, not a fabricated long position.

    Full long/short lineage is bound by observation_id and retained in Snapshot.
    The legacy assets field is empty; new per-episode marks live in Snapshot.
    """

    observation_id: str


class Snapshot(Contract):
    source: Observation
    accounting: ValuationPoint
    marks: tuple[Mark, ...]
    used_margin: Money | None
    free_margin: Money | None
    available_margin: Money | None
    gross_exposure: Money | None
    open_risk: Money | None
    reserved_risk: Money
    reserved_margin: Money
    reserved_exposure: Money
    nav: NavState
    risk_day: RiskDayState
    qualification_eligible: Literal[False] = False


def _mark(source: Observation) -> tuple[Mark, ...]:
    quotes = {q.instrument_id: q for q in source.quotes}
    at = source.book.cash.valuation_at
    marks = []
    for p in source.book.positions:
        e = p.economics
        quote = quotes.get(e.instrument_id)
        reason = None
        if not e.validation_reference or not e.valid_from <= at < e.valid_until:
            reason = "UNVALIDATED_OR_EXPIRED_ECONOMICS"
        elif quote is None:
            reason = "MISSING_MARK"
        pnl = risk = gross = margin = None
        if reason is None:
            assert quote is not None
            price = quote.bid if p.direction == "LONG" else quote.ask
            sign = Decimal(1) if p.direction == "LONG" else Decimal(-1)
            pnl = sign * (price - p.weighted_entry) * p.quantity * e.usd_per_price_unit_per_lot
            risk = (
                max(ZERO, sign * (price - p.fixed_stop)) + e.tick_size
            ) * p.quantity * e.usd_per_price_unit_per_lot + (
                p.quantity * e.commission_per_lot_per_side + e.commission_fixed_per_side
            )
            gross = p.quantity * price * e.contract_size
            margin = p.quantity * e.margin_per_lot
        marks.append(
            Mark(
                episode_id=p.episode_id,
                unrealized_pnl=pnl,
                stop_risk=risk,
                gross_notional=gross,
                margin=margin,
                unavailable_reason=reason,
                stale=quote is None or at - quote.at > timedelta(seconds=5),
            )
        )
    return tuple(marks)


def project(history: tuple[Observation, ...]) -> Snapshot:
    if not history:
        raise ValueError("PORTFOLIO_HISTORY_REQUIRED")
    sources = tuple(Observation.model_validate(o) for o in history)
    points = []
    marks: tuple[Mark, ...] = ()
    with arithmetic_context():
        for index, source in enumerate(sources):
            cash = source.book.cash
            if index:
                previous = sources[index - 1].book.cash
                if (
                    cash.account_id != previous.account_id
                    or cash.opening_at != previous.opening_at
                    or cash.opening_cash != previous.opening_cash
                    or cash.valuation_at < previous.valuation_at
                    or cash.reconciled_at < previous.reconciled_at
                    or cash.ledger[: len(previous.ledger)] != previous.ledger
                    or any(
                        e.effective_at < previous.valuation_at
                        for e in cash.ledger[len(previous.ledger) :]
                    )
                ):
                    raise ValueError("PORTFOLIO_APPEND_ONLY_HISTORY_MISMATCH")
            marks = _mark(source)
            complete = all(m.unavailable_reason is None for m in marks)
            floating = (
                sum((m.unrealized_pnl for m in marks if m.unrealized_pnl is not None), ZERO)
                if complete
                else None
            )
            balance = project_balance(cash)
            points.append(
                ValuationPoint(
                    observation_id=source.identity,
                    source=cash,
                    ledger_sequence=len(cash.ledger),
                    balance=balance,
                    assets=(),
                    unrealized_pnl=floating,
                    equity=balance.cash_balance + floating if floating is not None else None,
                    complete=complete,
                    stale=any(m.stale for m in marks)
                    or cash.valuation_at - cash.reconciled_at > timedelta(seconds=15),
                    open_episode_count=len(source.book.positions),
                    reserved_episode_count=len(source.reservations),
                )
            )
        current = points[-1]
        used = (
            sum((m.margin for m in marks if m.margin is not None), ZERO)
            if current.complete
            else None
        )
        gross = (
            sum((m.gross_notional for m in marks if m.gross_notional is not None), ZERO)
            if current.complete
            else None
        )
        risk = (
            sum((m.stop_risk for m in marks if m.stop_risk is not None), ZERO)
            if current.complete
            else None
        )
        reserves = sources[-1].reservations
        # Reconciled supplied totals can include account charges/margin outside
        # the explicit linear model; never understate them with a smaller model.
        cash = sources[-1].book.cash
        if used is not None and cash.used_margin is not None:
            used = max(used, cash.used_margin)
        if risk is not None and cash.open_stop_risk is not None:
            risk = max(risk, cash.open_stop_risk)
        reserved_margin = sum((r.margin for r in reserves), ZERO)
        reserved_risk = sum((r.stop_risk for r in reserves), ZERO)
        if cash.reserved_margin is not None:
            reserved_margin = max(reserved_margin, cash.reserved_margin)
        if cash.reserved_stop_risk is not None:
            reserved_risk = max(reserved_risk, cash.reserved_stop_risk)
        return Snapshot(
            source=sources[-1],
            accounting=current,
            marks=marks,
            used_margin=used,
            free_margin=current.equity - used
            if current.equity is not None and used is not None
            else None,
            available_margin=current.equity - used - reserved_margin
            if current.equity is not None and used is not None
            else None,
            gross_exposure=gross,
            open_risk=risk,
            reserved_risk=reserved_risk,
            reserved_margin=reserved_margin,
            reserved_exposure=sum((r.gross_notional for r in reserves), ZERO),
            nav=_nav(tuple(points)),
            risk_day=_day(tuple(points)),
        )
