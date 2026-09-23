"""Observation-only SDK adapter; reuses the existing native loader and bar read API."""

from datetime import datetime

from trading_ecosystem.mt5.client import ACCOUNT, ORDER, NativeReadClient, Record
from trading_ecosystem.mt5.normalization import normalize
from trading_ecosystem.observer.context import TIMEFRAMES

OBSERVER_READ_METHODS = frozenset({"copy_rates_range"})


class NativeObserverClient(NativeReadClient):
    def account_info(self) -> Record:
        return self._record(self._sdk.account_info, (*ACCOUNT, "margin_mode"))

    def orders_get(self) -> tuple[Record, ...]:
        return self._rows(self._sdk.orders_get, (*ORDER, "sl", "tp"))

    def history_orders_get(self, start: datetime, end: datetime) -> tuple[Record, ...]:
        return self._rows(lambda: self._sdk.history_orders_get(start, end), (*ORDER, "sl", "tp"))

    def bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> tuple[Record, ...]:
        code = TIMEFRAMES[timeframe][0]
        rows = self._call(lambda: self._sdk.copy_rates_range(symbol, code, start, end))
        if len(rows) > 12000:
            raise ValueError("OBSERVER_BAR_WINDOW_LIMIT")
        fields = ("time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")
        return tuple(normalize({key: row[key].item() for key in fields}) for row in rows)
