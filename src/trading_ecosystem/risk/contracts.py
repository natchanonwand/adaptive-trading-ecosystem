"""Pinned policies and quantity-free strategy input; sized output is risk-owned."""

from datetime import timedelta
from typing import Literal, Self

from pydantic import Field, model_validator

from trading_ecosystem.accounting.contracts import Contract, Label
from trading_ecosystem.domain.primitives import (
    Asset,
    EntityId,
    Money,
    Price,
    Quantity,
    RuntimeMode,
    UtcTimestamp,
)
from trading_ecosystem.portfolio.contracts import (
    Direction,
    Economics,
    Observation,
    Quote,
    Reservation,
)

PolicyId = Literal["V0_CONSERVATIVE", "HR_DEMO_5PCT"]


class Policy(Contract):
    policy_id: PolicyId = "V0_CONSERVATIVE"

    @property
    def limits(self) -> tuple[str, str, str, str, int]:
        if self.policy_id == "V0_CONSERVATIVE":
            return ("0.0025", "0.0075", "0.015", "0.05", 3)
        return ("0.05", "0.10", "0.10", "0.30", 2)


class TradeIntent(Contract):
    intent_id: EntityId
    strategy_id: EntityId
    asset: Asset
    direction: Direction
    signal_at: UtcTimestamp
    expires_at: UtcTimestamp
    signal_close: Price
    atr: Price
    fixed_stop: Price

    @model_validator(mode="after")
    def valid(self) -> Self:
        if not self.signal_at < self.expires_at <= self.signal_at + timedelta(minutes=5):
            raise ValueError("INVALID_ENTRY_EXPIRY")
        return self


class Health(Contract):
    account_kind: Literal["SIMULATED", "DEMO", "REAL", "UNKNOWN"] = "UNKNOWN"
    broker_connected: bool = Field(default=False, strict=True)
    reconciled: bool = Field(default=False, strict=True)
    lease_valid: bool = Field(default=False, strict=True)
    approval_valid: bool = Field(default=False, strict=True)
    session_open: bool = Field(default=False, strict=True)
    calendar_validated: bool = Field(default=False, strict=True)
    protection_confirmed: bool = Field(default=False, strict=True)
    unknown_submission: bool = Field(default=True, strict=True)
    severe_breach: bool = Field(default=False, strict=True)


class RiskState(Contract):
    account_id: EntityId
    policy: Policy
    at: UtcTimestamp
    status: Literal["ACTIVE", "PAUSE_ENTRIES", "HALT_AND_FLATTEN"]
    reasons: tuple[str, ...]


class Request(Contract):
    intent: TradeIntent
    policy: Policy = Policy()
    mode: RuntimeMode
    at: UtcTimestamp
    health: Health
    economics: Economics | None
    quote: Quote | None
    history: tuple[Observation, ...]
    prior_state: RiskState | None = None


class OrderIntent(Contract):
    trade_intent: TradeIntent
    volume: Quantity
    reference_entry: Price
    fixed_stop: Price
    estimated_stop_risk: Money
    estimated_margin: Money
    gross_notional: Money
    expires_at: UtcTimestamp
    input_identity: Label
    qualification_eligible: Literal[False] = False


class Decision(Contract):
    state: RiskState
    accepted: bool
    reasons: tuple[str, ...]
    input_identity: Label
    snapshot_identity: Label
    order: OrderIntent | None
    reservation: Reservation | None
    qualification_eligible: Literal[False] = False
