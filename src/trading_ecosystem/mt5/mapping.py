"""Copy broker facts without reconstructing P/L or inferring strategy attribution."""

from datetime import datetime

from trading_ecosystem.monitoring.contracts import AccountView, PositionView
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import identity, number, timestamp


def account_view(row: Record) -> AccountView:
    return AccountView(
        domain_identity="MT5_OBSERVED_ACCOUNT_V1",
        balance=number(row["balance"]),
        equity=number(row["equity"]),
        unrealized_pnl=number(row["profit"]),
        used_margin=number(row["margin"]),
        free_margin=number(row["margin_free"]),
        realized_pnl=None,
        commissions=None,
        financing=None,
        stale=False,
        complete=False,
    )


def position_view(scope: object, row: Record, at: datetime, generation: int) -> PositionView:
    if row["type"] not in (0, 1):
        raise ValueError("UNKNOWN_POSITION_SIDE")

    def optional_price(name: str) -> str | None:
        value = number(row[name])
        return str(value) if value > 0 else None

    return PositionView(
        domain_identity="MT5_OBSERVED_POSITION_V1",
        episode_id=identity(scope, "POSITION", row["identifier"], row["ticket"], generation),
        side="LONG" if row["type"] == 0 else "SHORT",
        quantity=number(row["volume"]),
        average_entry=number(row["price_open"]),
        mark_price=optional_price("price_current"),
        unrealized_pnl=number(row["profit"]),
        realized_pnl=None,
        stop_loss=optional_price("sl"),
        take_profit=optional_price("tp"),
        opened_at=timestamp(row["time"], row.get("time_msc")),
        updated_at=at,
        state="OPEN",
    )
