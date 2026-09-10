"""Validated boundary types; monetary input never passes through binary float."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)


class Asset(StrEnum):
    BTCUSD = "BTCUSD"
    XAUUSD = "XAUUSD"
    USTEC100 = "USTEC100"


class RuntimeMode(StrEnum):
    RESEARCH = "RESEARCH"
    BACKTEST = "BACKTEST"
    PAPER_FORWARD = "PAPER_FORWARD"
    DEMO_QUALIFICATION = "DEMO_QUALIFICATION"
    DEMO_OPERATIONAL = "DEMO_OPERATIONAL"


def utc_timestamp(value: object) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("invalid UTC timestamp") from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(UTC)


def entity_id(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            pass
    raise ValueError("UUID required")


def finite_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise ValueError("Decimal, integer or decimal text required; floats forbidden")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError("invalid decimal") from None
    if not result.is_finite():
        raise ValueError("finite decimal required")
    # A bounded representation avoids pathological canonicalization/storage sizes.
    if len(result.as_tuple().digits) > 34 or abs(int(result.as_tuple().exponent)) > 100:
        raise ValueError("decimal exceeds the 34-digit / exponent-100 boundary")
    return result


def positive_decimal(value: object) -> Decimal:
    result = finite_decimal(value)
    if result <= 0:
        raise ValueError("positive decimal required")
    return result


EntityId = Annotated[UUID, BeforeValidator(entity_id)]
CorrelationId = Annotated[UUID, BeforeValidator(entity_id)]
CausationId = Annotated[UUID, BeforeValidator(entity_id)]
UtcTimestamp = Annotated[datetime, BeforeValidator(utc_timestamp)]
Money = Annotated[Decimal, BeforeValidator(finite_decimal)]
Price = Annotated[Decimal, BeforeValidator(positive_decimal)]
Quantity = Annotated[Decimal, BeforeValidator(positive_decimal)]
AccountSequence = Annotated[int, Field(strict=True, ge=1, le=2**63 - 1)]


class MoneyAmount(FrozenModel):
    amount: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class PriceAmount(FrozenModel):
    value: Price
    asset: Asset


class QuantityAmount(FrozenModel):
    value: Quantity
    unit: str = Field(min_length=1, max_length=32)
