"""Balance and explicit instrument-specific BID valuation, without I/O."""

from datetime import timedelta
from decimal import Decimal

from trading_ecosystem.accounting.contracts import (
    AccountInput,
    AssetValuation,
    Balance,
    Category,
    EquitySnapshot,
    LongPosition,
)
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import Asset, UtcTimestamp

ZERO = Decimal(0)


def project_balance(source: AccountInput) -> Balance:
    source = AccountInput.model_validate(source)
    with arithmetic_context():
        totals = {
            category: sum((e.amount for e in source.ledger if e.category == category), ZERO)
            for category in Category
        }
        return Balance(
            opening_cash=source.opening_cash,
            external_cash_flows=totals[Category.CASH_FLOW],
            realized_pnl=totals[Category.REALIZED_PNL],
            commissions=totals[Category.COMMISSION],
            financing=totals[Category.FINANCING],
            audited_adjustments=totals[Category.ADJUSTMENT],
            cash_balance=source.opening_cash + sum(totals.values(), ZERO),
        )


def _position_value(position: LongPosition, time: UtcTimestamp) -> AssetValuation:
    model = position.valuation_model
    reason = None
    if position.current_bid is None:
        reason = "MISSING_BID_QUOTE"
    elif model is None or model.validation_reference is None:
        reason = "MISSING_VALIDATED_USD_MODEL"
    elif (
        model.asset != position.asset
        or model.instrument_id != position.instrument_id
        or model.quantity_unit != position.quantity_unit
        or model.price_unit != position.price_unit
    ):
        reason = "VALUATION_MODEL_UNIT_OR_INSTRUMENT_MISMATCH"
    elif not model.valid_from <= time < model.valid_until:
        reason = "VALUATION_MODEL_OUTSIDE_EFFECTIVE_INTERVAL"
    pnl = None
    if reason is None:
        assert model is not None and position.current_bid is not None
        pnl = (
            position.quantity
            * (position.current_bid - position.weighted_actual_entry)
            * model.usd_per_quantity_price_unit
        )
    return AssetValuation(
        asset=position.asset,
        position=position,
        reserved_episode=None,
        unrealized_pnl=pnl,
        stale=position.quote_at is None or time - position.quote_at > timedelta(seconds=5),
        unavailable_reason=reason,
    )


def project_equity(source: AccountInput) -> EquitySnapshot:
    """Stale known marks remain visible; missing marks propagate unknown equity."""
    source = AccountInput.model_validate(source)
    with arithmetic_context():
        balance = project_balance(source)
        positions = {item.asset: item for item in source.positions}
        reservations = {item.asset: item for item in source.reservations}
        assets = tuple(
            _position_value(positions[asset], source.valuation_at)
            if asset in positions
            else AssetValuation(
                asset=asset,
                position=None,
                reserved_episode=reservations[asset].episode_id if asset in reservations else None,
                unrealized_pnl=ZERO,
                stale=False,
                unavailable_reason=None,
            )
            for asset in sorted(Asset, key=lambda asset: asset.value)
        )
        complete = all(item.unrealized_pnl is not None for item in assets)
        floating = (
            sum((item.unrealized_pnl for item in assets if item.unrealized_pnl is not None), ZERO)
            if complete
            else None
        )
        return EquitySnapshot(
            source=source,
            ledger_sequence=len(source.ledger),
            balance=balance,
            assets=assets,
            unrealized_pnl=floating,
            equity=balance.cash_balance + floating if floating is not None else None,
            complete=complete,
            stale=any(item.stale for item in assets)
            or source.valuation_at - source.reconciled_at > timedelta(seconds=15),
            open_episode_count=len(source.positions),
            reserved_episode_count=len(source.reservations),
        )
