"""Separate calculation evidence, conditional experiments and qualification admission."""

from datetime import timedelta
from decimal import Decimal
from typing import Literal

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import FrozenModel
from trading_ecosystem.mt5.economics import (
    BrokerInstrumentSnapshot,
    ValidatedCosts,
    to_economics,
)
from trading_ecosystem.mt5.normalization import number
from trading_ecosystem.portfolio.contracts import Economics

EvidenceStatus = Literal["VALIDATED", "OBSERVED_ONLY", "UNKNOWN", "FAIL"]


class BrokerEconomicsEvidence(FrozenModel):
    snapshot: BrokerInstrumentSnapshot
    price_pnl_model: EvidenceStatus
    volume_lattice: EvidenceStatus
    tick_economics: EvidenceStatus
    margin_estimate: EvidenceStatus
    commission_model: EvidenceStatus = "UNKNOWN"
    swap_model: EvidenceStatus = "UNKNOWN"
    stop_constraints: EvidenceStatus
    qualification_eligible: Literal[False] = False

    @property
    def risk_sizing_ready(self) -> bool:
        return all(
            getattr(self, field) == "VALIDATED"
            for field in (
                "price_pnl_model",
                "volume_lattice",
                "tick_economics",
                "margin_estimate",
                "commission_model",
                "swap_model",
                "stop_constraints",
            )
        ) and self.snapshot.status not in {"INVALID", "UNAVAILABLE"}


def qualified_economics(
    evidence: BrokerEconomicsEvidence, costs: ValidatedCosts | None
) -> Economics:
    if not evidence.risk_sizing_ready:
        raise ValueError("BROKER_ECONOMICS_NOT_SIZING_READY")
    return to_economics(evidence.snapshot, costs)


def conditional_economics(snapshot: BrokerInstrumentSnapshot, margin: Decimal) -> Economics:
    """Explicit experiment: $1/lot/side plus $0.01/side; not inferred or qualified.

    Swap is outside the instantaneous stop-loss experiment. These assumptions
    exercise the unchanged engine's fee arithmetic, not the broker's fee schedule.
    This helper is not used by the bridge, API, or qualification adapter.
    """
    return to_economics(
        snapshot,
        ValidatedCosts(
            margin_per_lot=margin,
            commission_per_lot_per_side=Decimal("1"),
            commission_fixed_per_side=Decimal("0.01"),
            reference="CONDITIONAL_CALIBRATION_EXPERIMENT_NOT_BROKER_COST_VALIDATION",
            valid_until=snapshot.observed_at + timedelta(minutes=5),
        ),
    )


def constraints(snapshot: BrokerInstrumentSnapshot) -> dict[str, str]:
    m = snapshot.metadata
    with arithmetic_context():
        digits = m.get("digits")
        if type(digits) is not int or not 0 <= digits <= 12:
            raise ValueError("INVALID_PRICE_DIGITS")
        point, tick = number(m["point"]), number(m["trade_tick_size"])
        if point != Decimal(1).scaleb(-digits) or tick <= 0 or tick % point:
            raise ValueError("INVALID_PRICE_LATTICE")
        result = {}
        for field in ("trade_stops_level", "trade_freeze_level"):
            value = number(m[field])
            if value < 0 or value != value.to_integral_value():
                raise ValueError("INVALID_STOP_FREEZE_LEVEL")
            result[field + "_price_distance"] = str(value * point)
        return result


def valid_volume(value: Decimal, snapshot: BrokerInstrumentSnapshot) -> bool:
    with arithmetic_context():
        m = snapshot.metadata
        low, high, step = (number(m[k]) for k in ("volume_min", "volume_max", "volume_step"))
        return step > 0 and low > 0 and low <= value <= high and (value - low) % step == 0
