"""The sole numeric conversion boundary for external discovery observations."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from numbers import Integral, Real

from trading_ecosystem.discovery.contracts import Instrument
from trading_ecosystem.domain.primitives import finite_decimal

DECIMAL_FIELDS = (
    "point",
    "trade_tick_size",
    "trade_tick_value",
    "trade_tick_value_profit",
    "trade_tick_value_loss",
    "trade_contract_size",
    "volume_min",
    "volume_max",
    "volume_step",
    "volume_limit",
    "swap_long",
    "swap_short",
    "bid",
    "ask",
)
INTEGER_FIELDS = (
    "digits",
    "trade_stops_level",
    "trade_freeze_level",
    "trade_calc_mode",
    "trade_mode",
    "trade_exemode",
    "filling_mode",
    "order_mode",
    "swap_mode",
    "swap_rollover3days",
)
TEXT_FIELDS = ("description", "path", "currency_base", "currency_profit", "currency_margin")


def source_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        return None
    try:
        # SDK doubles are converted once through their decimal text; domain
        # arithmetic and storage never retain a binary float.
        return finite_decimal(str(value))
    except ValueError:
        return None


def source_integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, Integral)):
        return None
    return int(value)


def safe_text(value: object) -> str | None:
    return value if isinstance(value, str) and value and len(value) <= 512 else None


def instrument(fields: Mapping[str, object]) -> Instrument:
    name = safe_text(fields.get("name"))
    if name is None:
        raise ValueError("INVALID_SYMBOL_NAME")
    return Instrument(
        broker_symbol=name,
        description=safe_text(fields.get("description")),
        path=safe_text(fields.get("path")),
        currency_base=safe_text(fields.get("currency_base")),
        currency_profit=safe_text(fields.get("currency_profit")),
        currency_margin=safe_text(fields.get("currency_margin")),
    )


def source_time(fields: Mapping[str, object]) -> tuple[datetime, bool]:
    millis = source_integer(fields.get("time_msc"))
    seconds = source_integer(fields.get("time"))
    if millis is not None and millis > 0:
        return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=millis), True
    if seconds is not None and seconds > 0:
        return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds), False
    raise ValueError("INVALID_SOURCE_TIME")
