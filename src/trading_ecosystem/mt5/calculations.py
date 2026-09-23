"""Authorized calculation boundary; no request construction or execution capability."""

from decimal import Decimal
from typing import Literal, Protocol

from trading_ecosystem.mt5.client import NativeReadClient
from trading_ecosystem.mt5.normalization import number

Side = Literal["BUY", "SELL"]
READ_METHODS = frozenset(
    {
        "initialize",
        "shutdown",
        "last_error",
        "terminal_info",
        "account_info",
        "symbols_get",
        "symbol_info",
        "symbol_info_tick",
        "positions_get",
        "orders_get",
        "history_deals_get",
        "history_orders_get",
    }
)
CALCULATION_METHODS = frozenset({"order_calc_profit", "order_calc_margin"})
FORBIDDEN_TRADING_METHODS = frozenset({"order_" + "send", "order_check", "login"})


class Calculator(Protocol):
    def profit(
        self, side: Side, symbol: str, volume: Decimal, opened: Decimal, closed: Decimal
    ) -> Decimal: ...

    def margin(self, side: Side, symbol: str, volume: Decimal, price: Decimal) -> Decimal: ...


def action(side: Side) -> int:
    if side not in {"BUY", "SELL"}:
        raise ValueError("INVALID_CALCULATION_SIDE")
    # Documented ENUM_ORDER_TYPE values; these are calculator arguments, not requests.
    return 0 if side == "BUY" else 1


def positive(value: Decimal) -> float:
    value = number(value)
    if value <= 0:
        raise ValueError("NONPOSITIVE_CALCULATION_ARGUMENT")
    return float(value)


class NativeCalculator(NativeReadClient):
    def profit(
        self, side: Side, symbol: str, volume: Decimal, opened: Decimal, closed: Decimal
    ) -> Decimal:
        args = action(side), symbol, positive(volume), positive(opened), positive(closed)
        return number(self._call(lambda: self._sdk.order_calc_profit(*args)))

    def margin(self, side: Side, symbol: str, volume: Decimal, price: Decimal) -> Decimal:
        args = action(side), symbol, positive(volume), positive(price)
        result = number(self._call(lambda: self._sdk.order_calc_margin(*args)))
        if result < 0:
            raise ValueError("NEGATIVE_CALCULATED_MARGIN")
        return result
