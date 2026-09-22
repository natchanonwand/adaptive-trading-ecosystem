from datetime import UTC, datetime
from uuid import uuid4

from trading_ecosystem.mt5.client import ReadError, Record

T = datetime(2026, 9, 22, 0, 0, tzinfo=UTC)


def instrument() -> Record:
    return dict(
        name="TEST.b",
        digits=2,
        point=0.01,
        trade_tick_size=0.01,
        trade_tick_value=1.0,
        trade_tick_value_profit=1.0,
        trade_tick_value_loss=1.0,
        trade_contract_size=100.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_stops_level=10,
        trade_freeze_level=0,
        currency_base="XAU",
        currency_profit="USD",
        currency_margin="USD",
        margin_initial=0.0,
        margin_maintenance=0.0,
        trade_mode=4,
    )


def position(ticket: int = 1, side: int = 0) -> Record:
    return dict(
        ticket=ticket,
        identifier=ticket,
        time=int(T.timestamp()) - 100,
        time_msc=int(T.timestamp()) * 1000 - 100000,
        time_update=int(T.timestamp()),
        time_update_msc=int(T.timestamp()) * 1000,
        type=side,
        magic=77,
        comment="external EA",
        volume=0.1,
        price_open=2000.0,
        price_current=2001.0,
        sl=1900.0,
        tp=2100.0,
        profit=10.0,
        swap=-0.1,
        symbol="TEST.b",
    )


def deal(ticket: int = 1) -> Record:
    return dict(
        ticket=ticket,
        order=3,
        position_id=1,
        time=int(T.timestamp()) - 1,
        time_msc=int(T.timestamp()) * 1000 - 1000,
        type=0,
        entry=1,
        magic=77,
        comment="external EA",
        volume=0.1,
        price=2001.0,
        commission=-0.2,
        swap=-0.1,
        profit=10.0,
        fee=0.0,
        symbol="TEST.b",
        reason=3,
    )


class FakeClient:
    def __init__(self) -> None:
        self.account: Record = dict(
            login=uuid4().int % 1000000000,
            server="TEST-DEMO",
            company="Fixture",
            trade_mode=0,
            currency="USD",
            leverage=100,
            balance=10000.0,
            equity=10010.0,
            profit=10.0,
            margin=100.0,
            margin_free=9910.0,
            margin_level=10010.0,
        )
        self.terminal: Record = dict(
            connected=True, build=1, trade_allowed=False, tradeapi_disabled=True, ping_last=10
        )
        self.positions: tuple[Record, ...] = (position(),)
        self.orders: tuple[Record, ...] = ()
        self.deals: tuple[Record, ...] = (deal(),)
        self.history_orders: tuple[Record, ...] = ()
        self.metadata = instrument()
        self.tick: Record = dict(
            time=int(T.timestamp()),
            time_msc=int(T.timestamp()) * 1000,
            bid=2000.0,
            ask=2001.0,
            last=0.0,
            volume=0,
            flags=2,
        )
        self.fail: str | None = None
        self.initializes = 0
        self.shutdowns = 0
        self.windows: list[tuple[datetime, datetime]] = []

    def check(self, name: str) -> None:
        if self.fail == name:
            raise ReadError("MT5_API_ERROR_-1")

    def initialize(self) -> bool:
        self.initializes += 1
        return self.fail != "initialize"

    def shutdown(self) -> None:
        self.shutdowns += 1

    def terminal_info(self) -> Record:
        self.check("terminal")
        return self.terminal

    def account_info(self) -> Record:
        self.check("account")
        return self.account

    def symbols_get(self) -> tuple[Record, ...]:
        self.check("symbols")
        return ({"name": "TEST.b", "visible": True},)

    def symbol_info(self, symbol: str) -> Record:
        self.check("metadata")
        return self.metadata

    def symbol_info_tick(self, symbol: str) -> Record:
        self.check("tick")
        return self.tick

    def positions_get(self) -> tuple[Record, ...]:
        self.check("positions")
        return self.positions

    def orders_get(self) -> tuple[Record, ...]:
        self.check("orders")
        return self.orders

    def history_deals_get(self, start: datetime, end: datetime) -> tuple[Record, ...]:
        self.check("deals")
        self.windows.append((start, end))
        return tuple(
            row for row in self.deals if start.timestamp() <= row["time"] <= end.timestamp()
        )

    def history_orders_get(self, start: datetime, end: datetime) -> tuple[Record, ...]:
        self.check("history_orders")
        return self.history_orders
