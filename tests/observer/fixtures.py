from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from tests.mt5.fake import FakeClient, instrument
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import account_identity, normalize
from trading_ecosystem.observer.context import TIMEFRAMES
from trading_ecosystem.observer.contracts import Candidate, Config, Frame, ObservationSession

T = datetime(2026, 9, 23, 0, 0, tzinfo=UTC)
SYMBOLS = ("BTCUSDm", "XAUUSDm", "USTECm")


def config() -> Config:
    return Config(
        symbols=SYMBOLS,
        candidates=(
            Candidate(
                ea_id="fixture-a",
                display_name="Fixture EA A",
                magic_numbers=(77, 78),
                symbols=SYMBOLS,
                exclusive_binding=True,
                attribution_reference="DETERMINISTIC_FAKE_NOT_REAL_EA",
            ),
        ),
    )


def session(**updates: Any) -> ObservationSession:
    return ObservationSession.model_validate(
        dict(
            session_id=UUID(int=4001),
            account_scope=UUID(int=4002),
            broker="FIXTURE",
            server_scope="FAKE-DEMO",
            margin_mode=2,
            started_at=T,
            terminal_build=1,
            config=config(),
            **updates,
        )
    )


def position(**updates: Any) -> Record:
    return dict(
        ticket=100,
        identifier=100,
        symbol="BTCUSDm",
        magic=77,
        comment="fixture",
        type=0,
        volume="0.10",
        price_open="100",
        sl="95",
        tp="110",
        **updates,
    )


def trade(ticket: int, seconds: int, **updates: Any) -> Record:
    row = dict(
        ticket=ticket,
        order=ticket + 1000,
        position_id=100,
        symbol="BTCUSDm",
        magic=77,
        comment="fixture",
        type=0,
        entry=0,
        volume="0.10",
        price="100",
        commission="-.01",
        fee="0",
        swap="0",
        profit="0",
        time=int((T + timedelta(seconds=seconds)).timestamp()),
        time_msc=int((T + timedelta(seconds=seconds)).timestamp() * 1000),
    )
    return {**row, **updates}


def frame(
    sequence: int,
    *,
    positions: tuple[Record, ...] = (),
    deals: tuple[Record, ...] = (),
    **updates: Any,
) -> Frame:
    return Frame.model_validate(
        dict(
            session_id=UUID(int=4001),
            sequence=sequence,
            observed_at=T + timedelta(seconds=sequence),
            account={"equity": "10000", "balance": "10000"},
            positions=positions,
            orders=(),
            deals=deals,
            quotes={},
            metadata={s: normalize(instrument()) for s in SYMBOLS},
            **updates,
        )
    )


class FakeObserver(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.account.update(currency_digits=2, margin_mode=2)
        self.positions = ()
        self.orders = ()
        self.deals = ()
        self.history_orders = ()
        self.now = T

    def symbols_get(self) -> tuple[Record, ...]:
        return tuple({"name": s, "visible": True} for s in SYMBOLS)

    def symbol_info(self, symbol: str) -> Record:
        return {**instrument(), "name": symbol}

    def symbol_info_tick(self, symbol: str) -> Record:
        return dict(
            time=int(self.now.timestamp()),
            time_msc=int(self.now.timestamp() * 1000),
            bid=100.0,
            ask=100.01,
        )

    def bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> tuple[Record, ...]:
        seconds = TIMEFRAMES[timeframe][1]
        closed = int(end.timestamp()) // seconds * seconds
        return tuple(
            dict(
                time=closed - i * seconds,
                open="100",
                high="101",
                low="99",
                close="100",
                tick_volume=10,
                spread=1,
                real_volume=0,
            )
            for i in range(100, -1, -1)
        )

    def observation_session(self) -> ObservationSession:
        return session().model_copy(update={"account_scope": account_identity(self.account)})
