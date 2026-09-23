"""Reuse the frozen SDK loader; expose only the explicit Phase 4A read-method allowlist."""

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

Record = dict[str, Any]


class ReadError(RuntimeError):
    """Sanitized API failure: never includes native error text or credentials."""


class Mt5ReadClient(Protocol):
    def initialize(self) -> bool: ...
    def shutdown(self) -> None: ...
    def terminal_info(self) -> Record: ...
    def account_info(self) -> Record: ...
    def symbols_get(self) -> tuple[Record, ...]: ...
    def symbol_info(self, symbol: str) -> Record: ...
    def symbol_info_tick(self, symbol: str) -> Record: ...
    def positions_get(self) -> tuple[Record, ...]: ...
    def orders_get(self) -> tuple[Record, ...]: ...
    def history_deals_get(self, start: datetime, end: datetime) -> tuple[Record, ...]: ...
    def history_orders_get(self, start: datetime, end: datetime) -> tuple[Record, ...]: ...


ACCOUNT = (
    "login",
    "server",
    "company",
    "trade_mode",
    "currency",
    "currency_digits",
    "leverage",
    "balance",
    "equity",
    "profit",
    "margin",
    "margin_free",
    "margin_level",
)
TERMINAL = (
    "name",
    "company",
    "build",
    "connected",
    "trade_allowed",
    "tradeapi_disabled",
    "ping_last",
)
INSTRUMENT = (
    "name",
    "visible",
    "digits",
    "point",
    "trade_tick_size",
    "trade_tick_value",
    "trade_tick_value_profit",
    "trade_tick_value_loss",
    "trade_contract_size",
    "volume_min",
    "volume_max",
    "volume_step",
    "trade_stops_level",
    "trade_freeze_level",
    "currency_base",
    "currency_profit",
    "currency_margin",
    "margin_initial",
    "margin_maintenance",
    "trade_mode",
    "trade_calc_mode",
)
POSITION = (
    "ticket",
    "identifier",
    "time",
    "time_msc",
    "time_update",
    "time_update_msc",
    "type",
    "magic",
    "volume",
    "price_open",
    "price_current",
    "sl",
    "tp",
    "profit",
    "swap",
    "symbol",
    "comment",
)
ORDER = (
    "ticket",
    "time_setup",
    "time_setup_msc",
    "time_done",
    "time_done_msc",
    "type",
    "state",
    "magic",
    "position_id",
    "position_by_id",
    "volume_initial",
    "volume_current",
    "price_open",
    "price_current",
    "sl",
    "tp",
    "symbol",
    "comment",
)
DEAL = (
    "ticket",
    "order",
    "time",
    "time_msc",
    "type",
    "entry",
    "magic",
    "position_id",
    "reason",
    "volume",
    "price",
    "commission",
    "swap",
    "profit",
    "fee",
    "symbol",
    "comment",
)
TICK = ("time", "time_msc", "bid", "ask", "last", "volume", "volume_real", "flags")


class NativeReadClient:
    def __init__(self) -> None:
        from trading_ecosystem.discovery.sdk import NativeSdk

        # The existing loader remains the sole native import. This infrastructure
        # boundary deliberately borrows its module handle, never its wider methods.
        self._sdk = NativeSdk()._mt5

    def _call(self, operation: Callable[[], Any]) -> Any:
        try:
            result = operation()
        except Exception:
            raise ReadError("MT5_API_EXCEPTION") from None
        if result is None:
            error = self._sdk.last_error()
            code = error[0] if error and type(error[0]) is int else 0
            raise ReadError(f"MT5_API_ERROR_{code}")
        return result

    def initialize(self) -> bool:
        return bool(self._call(lambda: self._sdk.initialize(timeout=15000)))

    def shutdown(self) -> None:
        self._sdk.shutdown()

    def _record(self, call: Callable[[], Any], fields: tuple[str, ...]) -> Record:
        row = self._call(call)
        return {key: getattr(row, key, None) for key in fields}

    def _rows(self, call: Callable[[], Any], fields: tuple[str, ...]) -> tuple[Record, ...]:
        return tuple({key: getattr(row, key, None) for key in fields} for row in self._call(call))

    def terminal_info(self) -> Record:
        return self._record(self._sdk.terminal_info, TERMINAL)

    def account_info(self) -> Record:
        return self._record(self._sdk.account_info, ACCOUNT)

    def symbols_get(self) -> tuple[Record, ...]:
        return self._rows(self._sdk.symbols_get, ("name", "visible"))

    def symbol_info(self, symbol: str) -> Record:
        return self._record(lambda: self._sdk.symbol_info(symbol), INSTRUMENT)

    def symbol_info_tick(self, symbol: str) -> Record:
        return self._record(lambda: self._sdk.symbol_info_tick(symbol), TICK)

    def positions_get(self) -> tuple[Record, ...]:
        return self._rows(self._sdk.positions_get, POSITION)

    def orders_get(self) -> tuple[Record, ...]:
        return self._rows(self._sdk.orders_get, ORDER)

    def history_deals_get(self, start: datetime, end: datetime) -> tuple[Record, ...]:
        return self._rows(lambda: self._sdk.history_deals_get(start, end), DEAL)

    def history_orders_get(self, start: datetime, end: datetime) -> tuple[Record, ...]:
        return self._rows(lambda: self._sdk.history_orders_get(start, end), ORDER)
