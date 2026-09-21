"""Copy authoritative Phase 3.4 values; no monitoring accounting formula."""

from decimal import Decimal
from uuid import UUID

from trading_ecosystem.domain.primitives import Money, Price, UtcTimestamp
from trading_ecosystem.monitoring.contracts import (
    AccountView,
    PortfolioView,
    PositionView,
    RiskView,
)
from trading_ecosystem.portfolio.projection import Snapshot
from trading_ecosystem.risk.contracts import Decision, RiskState


def account_view(snapshot: Snapshot) -> AccountView:
    a = snapshot.accounting
    return AccountView(
        domain_identity=snapshot.identity,
        balance=a.balance.cash_balance,
        equity=a.equity,
        realized_pnl=a.balance.realized_pnl,
        unrealized_pnl=a.unrealized_pnl,
        commissions=a.balance.commissions,
        financing=a.balance.financing,
        used_margin=snapshot.used_margin,
        free_margin=snapshot.free_margin,
        stale=a.stale,
        complete=a.complete,
    )


def portfolio_view(snapshot: Snapshot, state: RiskState | None = None) -> PortfolioView:
    if state is not None and state.account_id != snapshot.source.book.cash.account_id:
        raise ValueError("RISK_ACCOUNT_MISMATCH")
    return PortfolioView(
        account=account_view(snapshot),
        gross_exposure=snapshot.gross_exposure,
        open_risk=snapshot.open_risk,
        reserved_risk=snapshot.reserved_risk,
        daily_pnl=snapshot.risk_day.today_trading_pnl,
        peak_nav=snapshot.nav.high_water_mark,
        drawdown=snapshot.nav.drawdown,
        risk_state=state.status if state else None,
        open_positions=snapshot.accounting.open_episode_count,
        reserved_positions=snapshot.accounting.reserved_episode_count,
    )


def position_view(
    snapshot: Snapshot,
    episode_id: UUID,
    opened_at: UtcTimestamp,
    realized_pnl: Money | None = None,
    take_profit: Price | None = None,
) -> PositionView:
    p = next(p for p in snapshot.source.book.positions if p.episode_id == episode_id)
    mark = next(m for m in snapshot.marks if m.episode_id == episode_id)
    quote = next(
        (q for q in snapshot.source.quotes if q.instrument_id == p.economics.instrument_id), None
    )
    price = None if quote is None else quote.bid if p.direction == "LONG" else quote.ask
    return PositionView(
        domain_identity=snapshot.identity,
        episode_id=p.episode_id,
        side=p.direction,
        quantity=p.quantity,
        average_entry=p.weighted_entry,
        mark_price=price,
        unrealized_pnl=mark.unrealized_pnl,
        realized_pnl=realized_pnl,
        stop_loss=p.fixed_stop,
        take_profit=take_profit,
        opened_at=opened_at,
        updated_at=snapshot.source.book.cash.valuation_at,
        state="OPEN",
    )


def risk_view(decision: Decision, snapshot: Snapshot) -> RiskView:
    if decision.snapshot_identity != snapshot.identity:
        raise ValueError("DECISION_SNAPSHOT_MISMATCH")
    trade, aggregate, daily, drawdown, _ = decision.state.policy.limits
    return RiskView(
        domain_identity=decision.identity,
        policy_id=decision.state.policy.policy_id,
        risk_state=decision.state.status,
        risk_per_trade=Decimal(trade),
        open_risk=snapshot.open_risk,
        portfolio_risk_limit=Decimal(aggregate),
        daily_loss=snapshot.risk_day.daily_loss_fraction,
        daily_loss_limit=Decimal(daily),
        drawdown=snapshot.nav.drawdown,
        drawdown_limit=Decimal(drawdown),
        rejection_reasons=decision.reasons,
    )
