"""Only this module imports the optional Windows SDK. No native records escape."""

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from trading_ecosystem.discovery.contracts import DiscoveryError
from trading_ecosystem.discovery.normalization import DECIMAL_FIELDS, INTEGER_FIELDS, TEXT_FIELDS


class DiscoverySdk(Protocol):
    def initialize(self) -> bool: ...
    def shutdown(self) -> None: ...
    def account_info(self) -> Mapping[str, object] | None: ...
    def terminal_info(self) -> Mapping[str, object] | None: ...
    def symbols_get(self) -> tuple[Mapping[str, object], ...]: ...
    def symbol_info(self, symbol: str) -> Mapping[str, object] | None: ...
    def symbol_info_tick(self, symbol: str) -> Mapping[str, object] | None: ...
    def symbol_select(self, symbol: str, selected: bool) -> bool: ...
    def copy_rates_range(
        self, symbol: str, start: datetime, end: datetime
    ) -> Sequence[Mapping[str, object]] | None: ...
    def copy_ticks_range(
        self, symbol: str, start: datetime, end: datetime
    ) -> Sequence[Mapping[str, object]] | None: ...


def _safe(call: Callable[[], Any]) -> Any:
    failed = False
    result = None
    try:
        result = call()
    except Exception:
        failed = True
    if failed:
        raise DiscoveryError("SDK_REQUEST_FAILED")
    return result


def _fields(record: object, names: tuple[str, ...]) -> dict[str, object] | None:
    if record is None:
        return None
    return {name: getattr(record, name, None) for name in names}


class NativeSdk:
    def __init__(self) -> None:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            raise DiscoveryError("WINDOWS_DISCOVERY_DEPENDENCY_REQUIRED") from None
        self._mt5 = mt5

    def initialize(self) -> bool:
        # Attach to the current terminal using stored terminal state only.
        # No account credentials, account selection, or login arguments exist.
        return bool(_safe(lambda: self._mt5.initialize(timeout=15_000)))

    def shutdown(self) -> None:
        _safe(lambda: self._mt5.shutdown())

    def account_info(self) -> Mapping[str, object] | None:
        return _fields(
            _safe(lambda: self._mt5.account_info()), ("company", "server", "currency", "trade_mode")
        )

    def terminal_info(self) -> Mapping[str, object] | None:
        return _fields(_safe(lambda: self._mt5.terminal_info()), ("connected", "maxbars"))

    def symbols_get(self) -> tuple[Mapping[str, object], ...]:
        records = _safe(lambda: self._mt5.symbols_get())
        if records is None:
            raise DiscoveryError("SYMBOL_CATALOG_UNAVAILABLE")
        return tuple(_fields(row, ("name", *TEXT_FIELDS)) or {} for row in records)

    def symbol_info(self, symbol: str) -> Mapping[str, object] | None:
        return _fields(
            _safe(lambda: self._mt5.symbol_info(symbol)),
            ("name", *TEXT_FIELDS, *DECIMAL_FIELDS, *INTEGER_FIELDS),
        )

    def symbol_info_tick(self, symbol: str) -> Mapping[str, object] | None:
        return _fields(
            _safe(lambda: self._mt5.symbol_info_tick(symbol)), ("time", "time_msc", "bid", "ask")
        )

    def symbol_select(self, symbol: str, selected: bool) -> bool:
        return bool(_safe(lambda: self._mt5.symbol_select(symbol, selected)))

    def copy_rates_range(
        self, symbol: str, start: datetime, end: datetime
    ) -> Sequence[Mapping[str, object]] | None:
        rows = _safe(lambda: self._mt5.copy_rates_range(symbol, self._mt5.TIMEFRAME_H1, start, end))
        if rows is None:
            return None
        return tuple(
            {name: row[name] for name in ("time", "open", "high", "low", "close")} for row in rows
        )

    def copy_ticks_range(
        self, symbol: str, start: datetime, end: datetime
    ) -> Sequence[Mapping[str, object]] | None:
        rows = _safe(
            lambda: self._mt5.copy_ticks_range(symbol, start, end, self._mt5.COPY_TICKS_INFO)
        )
        if rows is None:
            return None
        # One extra row signals truncation without materializing the entire raw
        # SDK result as Python records. Per-call windows are limited to one hour.
        return tuple(
            {
                name: row[name]
                for name in ("time", "time_msc", "bid", "ask")
                if name in rows.dtype.names
            }
            for row in rows[:100_001]
        )
