"""Unitized NAV replay and separate UTC midnight loss projection."""

from decimal import Decimal

from trading_ecosystem.accounting.contracts import (
    AccountInput,
    Category,
    EquitySnapshot,
    NavState,
    PortfolioSnapshot,
    RiskDayState,
)
from trading_ecosystem.accounting.projection import ZERO, project_equity
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.canonical import canonical_bytes, digest

ONE = Decimal(1)


def _ratio_at_most(numerator: Decimal, denominator: Decimal, n: int, d: int) -> bool:
    """Exact threshold comparison of finite Decimals, before display rounding."""
    an, ad = numerator.as_integer_ratio()
    bn, bd = denominator.as_integer_ratio()
    assert denominator > 0
    return an * bd * d <= bn * ad * n


def _history(inputs: tuple[AccountInput, ...]) -> tuple[EquitySnapshot, ...]:
    if not inputs:
        raise ValueError("ACCOUNTING_HISTORY_REQUIRED")
    snapshots = tuple(project_equity(item) for item in inputs)
    for previous, current in zip(snapshots, snapshots[1:], strict=False):
        before, after = previous.source, current.source
        if (
            after.account_id != before.account_id
            or after.opening_at != before.opening_at
            or after.opening_cash != before.opening_cash
            or after.valuation_at < before.valuation_at
            or after.reconciled_at < before.reconciled_at
            or len(after.ledger) < len(before.ledger)
            or after.ledger[: len(before.ledger)] != before.ledger
        ):
            raise ValueError("HISTORY_ACCOUNT_ORDER_OR_APPEND_ONLY_VIOLATION")
        if any(e.effective_at < before.valuation_at for e in after.ledger[len(before.ledger) :]):
            raise ValueError("LATE_ENTRY_REQUIRES_EXPLICIT_HISTORY_RECONSTRUCTION")
        if previous.identity == current.identity:
            raise ValueError("DUPLICATE_VALUATION_POINT")
    return snapshots


def _nav(snapshots: tuple[EquitySnapshot, ...]) -> NavState:
    first = snapshots[0]
    units, nav, high = first.equity, ONE, ONE
    reason = None
    if first.source.ledger or first.source.valuation_at != first.source.opening_at:
        reason = "MISSING_NAV_INCEPTION_VALUATION"
    if units is None or units <= 0:
        reason = "NONPOSITIVE_OR_UNKNOWN_INCEPTION_EQUITY"
    valid_points = 0
    for index, current in enumerate(snapshots):
        if not current.complete or current.stale:
            reason = reason or "INCOMPLETE_OR_STALE_NAV_HISTORY"
        if reason:
            break
        assert units is not None and current.equity is not None
        if index:
            previous = snapshots[index - 1]
            entries = current.source.ledger[previous.ledger_sequence :]
            flows = [entry for entry in entries if entry.category == Category.CASH_FLOW]
            if flows:
                # Each flow has adjacent, same-time pre/post valuations. Netting
                # multiple deposits/withdrawals would hide missing pre-flow NAV.
                flow = flows[0]
                if (
                    len(entries) != 1
                    or previous.source.valuation_at != flow.effective_at
                    or current.source.valuation_at != flow.effective_at
                    or previous.equity is None
                    or current.equity != previous.equity + flow.amount
                ):
                    reason = "MISSING_IMMEDIATE_PRE_OR_POST_FLOW_VALUATION"
                    break
                if nav <= 0:
                    reason = "NONPOSITIVE_PRE_FLOW_NAV"
                    break
                units += flow.amount / nav
                if units <= 0 or current.equity <= 0:
                    reason = "FLOW_EXHAUSTED_OR_EXCEEDED_ACCOUNT_UNITS"
                    break
                # Preserve NAV exactly at a pure cash-flow boundary.
            else:
                nav = current.equity / units
        high = max(high, nav)
        valid_points += 1
    return NavState(
        units=units if reason is None else None,
        nav=nav if reason is None else None,
        high_water_mark=high if valid_points else None,
        drawdown=ONE - nav / high if reason is None else None,
        drawdown_triggered=_ratio_at_most(nav, high, 95, 100) if reason is None else None,
        unavailable_reason=reason,
    )


def _day(snapshots: tuple[EquitySnapshot, ...]) -> RiskDayState:
    current = snapshots[-1]
    midnight = current.source.valuation_at.replace(hour=0, minute=0, second=0, microsecond=0)
    # The earliest point at midnight is the pre-flow boundary when a cash flow
    # occurs at midnight. Subsequent flows are recognized by sequence, not date.
    boundary = next((s for s in snapshots if s.source.valuation_at == midnight), None)
    reason = None
    if boundary is None or boundary.equity is None or boundary.equity <= 0 or boundary.stale:
        reason = "MISSING_VALID_UTC_MIDNIGHT_VALUATION"
    elif any(
        e.category == Category.CASH_FLOW and e.effective_at == midnight
        for e in boundary.source.ledger
    ):
        reason = "MISSING_PRE_FLOW_UTC_MIDNIGHT_VALUATION"
    elif not current.complete or current.stale:
        reason = "CURRENT_EQUITY_UNAVAILABLE_OR_STALE"
    flows = pnl = fraction = None
    triggered = None
    if reason is None:
        assert boundary is not None and boundary.equity is not None and current.equity is not None
        flows = sum(
            (
                e.amount
                for e in current.source.ledger[boundary.ledger_sequence :]
                if e.category == Category.CASH_FLOW
            ),
            ZERO,
        )
        pnl = current.equity - boundary.equity - flows
        fraction = pnl / boundary.equity
        triggered = _ratio_at_most(pnl, boundary.equity, -15, 1000)
    return RiskDayState(
        boundary_at=midnight,
        boundary_snapshot_id=boundary.identity if boundary is not None else None,
        boundary_equity=boundary.equity if boundary is not None else None,
        net_external_flows=flows,
        today_trading_pnl=pnl,
        daily_loss_fraction=fraction,
        daily_loss_triggered=triggered,
        unavailable_reason=reason,
    )


def project_portfolio(inputs: tuple[AccountInput, ...]) -> PortfolioSnapshot:
    """Replay caller-supplied observations. Eligibility is accounting readiness only.

    Missing NAV history stays unavailable until the caller supplies reconstructed
    evidence; this function never resets a baseline or latches/resets risk halts.
    """
    with arithmetic_context():
        snapshots = _history(inputs)
        nav, day = _nav(snapshots), _day(snapshots)
        current = snapshots[-1]
        return PortfolioSnapshot(
            equity_snapshot=current,
            history_id=digest(canonical_bytes(tuple(item.identity for item in snapshots))),
            nav=nav,
            risk_day=day,
            accounting_entry_eligible=current.equity is not None
            and current.equity > 0
            and nav.unavailable_reason is None
            and day.unavailable_reason is None
            and nav.drawdown_triggered is False
            and day.daily_loss_triggered is False,
        )
