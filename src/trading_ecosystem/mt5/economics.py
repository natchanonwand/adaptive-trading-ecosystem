"""Metadata-first economics checks; absent fee/margin evidence never becomes zero."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import Asset, FrozenModel
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import normalize, number
from trading_ecosystem.portfolio.contracts import Economics


class BrokerInstrumentSnapshot(FrozenModel):
    logical_symbol: str
    broker_symbol: str
    observed_at: datetime
    metadata: Record
    status: Literal["VALIDATED", "PARTIAL", "INVALID", "UNAVAILABLE"]
    reasons: tuple[str, ...]
    sizing_eligible: Literal[False] = False


class ValidatedCosts(FrozenModel):
    """Separately reviewed constant USD cost model, never inferred from MT5 metadata."""

    margin_per_lot: Decimal = Field(ge=0)
    commission_per_lot_per_side: Decimal = Field(ge=0)
    commission_fixed_per_side: Decimal = Field(ge=0)
    reference: str = Field(min_length=1)
    valid_until: datetime


def inspect_instrument(
    logical: str, broker: str, row: Record | None, at: datetime, currency: str
) -> BrokerInstrumentSnapshot:
    values = normalize(row) if row else {}
    reasons: list[str] = []
    status: Literal["VALIDATED", "PARTIAL", "INVALID", "UNAVAILABLE"] = "PARTIAL"
    required = (
        "point",
        "trade_tick_size",
        "trade_tick_value",
        "trade_tick_value_profit",
        "trade_tick_value_loss",
        "trade_contract_size",
        "volume_min",
        "volume_max",
        "volume_step",
    )
    if not row:
        status, reasons = "UNAVAILABLE", ["SYMBOL_METADATA_UNAVAILABLE"]
    else:
        for key in required:
            try:
                if number(values.get(key)) <= 0:
                    reasons.append(f"NONPOSITIVE_{key}")
                    status = "INVALID"
            except ValueError:
                reasons.append(f"MISSING_OR_INVALID_{key}")
        if all(values.get(k) is not None for k in required) and not reasons:
            with arithmetic_context():
                tick = number(values["trade_tick_size"])
                tick_value = number(values["trade_tick_value"])
                if number(values["volume_min"]) > number(values["volume_max"]):
                    status = "INVALID"
                    reasons.append("VOLUME_RANGE_INVALID")
                if tick_value != tick * number(values["trade_contract_size"]):
                    reasons.append("LINEAR_USD_CONTRACT_NOT_CONFIRMED")
                if any(
                    number(values[k]) != tick_value
                    for k in ("trade_tick_value_profit", "trade_tick_value_loss")
                ):
                    reasons.append("ASYMMETRIC_TICK_VALUES")
        if currency != "USD" or values.get("currency_profit") != "USD":
            reasons.append("PHASE34_LINEAR_USD_MODEL_NOT_APPLICABLE")
        reasons.append("MARGIN_AND_COMMISSION_MODEL_NOT_VALIDATED_BY_METADATA")
    return BrokerInstrumentSnapshot(
        logical_symbol=logical,
        broker_symbol=broker,
        observed_at=at,
        metadata=values,
        status=status,
        reasons=tuple(reasons),
    )


def to_economics(snapshot: BrokerInstrumentSnapshot, costs: ValidatedCosts | None) -> Economics:
    if (
        costs is None
        or snapshot.status in {"INVALID", "UNAVAILABLE"}
        or any(
            reason != "MARGIN_AND_COMMISSION_MODEL_NOT_VALIDATED_BY_METADATA"
            for reason in snapshot.reasons
        )
    ):
        raise ValueError("BROKER_ECONOMICS_NOT_SIZING_QUALIFIED")
    m = snapshot.metadata
    with arithmetic_context():
        return Economics(
            instrument_id=snapshot.broker_symbol,
            asset=Asset(snapshot.logical_symbol),
            version="BROKER_METADATA_REVIEWED_V1",
            tick_size=number(m["trade_tick_size"]),
            tick_value_per_lot=number(m["trade_tick_value"]),
            contract_size=number(m["trade_contract_size"]),
            usd_per_price_unit_per_lot=number(m["trade_contract_size"]),
            volume_min=number(m["volume_min"]),
            volume_max=number(m["volume_max"]),
            volume_step=number(m["volume_step"]),
            margin_per_lot=costs.margin_per_lot,
            commission_per_lot_per_side=costs.commission_per_lot_per_side,
            commission_fixed_per_side=costs.commission_fixed_per_side,
            minimum_stop_distance=number(m["trade_stops_level"]) * number(m["point"]),
            valid_from=snapshot.observed_at,
            valid_until=costs.valid_until,
            validation_reference=costs.reference,
        )
