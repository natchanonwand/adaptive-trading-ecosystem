"""Canonical monitoring contracts; LIVE here grants no runtime capability."""

from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from trading_ecosystem.accounting.contracts import Contract, Count, Label, Nonnegative
from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.domain.primitives import (
    AccountSequence,
    Asset,
    EntityId,
    Money,
    Price,
    UtcTimestamp,
)


class Environment(StrEnum):
    BACKTEST = "BACKTEST"
    PAPER_FORWARD = "PAPER_FORWARD"
    DEMO = "DEMO"
    LIVE = "LIVE"


class EventType(StrEnum):
    ACCOUNT_SNAPSHOT = "ACCOUNT_SNAPSHOT"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_UPDATED = "POSITION_UPDATED"
    POSITION_CLOSED = "POSITION_CLOSED"
    ORDER_INTENT_CREATED = "ORDER_INTENT_CREATED"
    ORDER_INTENT_REJECTED = "ORDER_INTENT_REJECTED"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    RISK_STATE_CHANGED = "RISK_STATE_CHANGED"
    PORTFOLIO_SNAPSHOT = "PORTFOLIO_SNAPSHOT"
    BROKER_CONNECTED = "BROKER_CONNECTED"
    BROKER_DISCONNECTED = "BROKER_DISCONNECTED"
    BROKER_STALE = "BROKER_STALE"
    RECONCILIATION_STARTED = "RECONCILIATION_STARTED"
    RECONCILIATION_OK = "RECONCILIATION_OK"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    STRATEGY_STARTED = "STRATEGY_STARTED"
    STRATEGY_STOPPED = "STRATEGY_STOPPED"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    EA_STARTED = "EA_STARTED"
    EA_STOPPED = "EA_STOPPED"
    EA_HEALTH = "EA_HEALTH"
    EXECUTION_INCIDENT = "EXECUTION_INCIDENT"
    SYSTEM_STARTED = "SYSTEM_STARTED"
    SYSTEM_STOPPED = "SYSTEM_STOPPED"
    SYSTEM_HEALTH = "SYSTEM_HEALTH"


class Scope(Contract):
    environment: Environment
    run_id: EntityId | None = None
    account_id: EntityId | None = None

    @property
    def stream_id(self) -> UUID:
        return UUID(hex=digest(canonical_bytes(self.model_dump()))[:32])


class AccountView(Contract):
    kind: Literal["ACCOUNT"] = "ACCOUNT"
    domain_identity: Label
    balance: Money
    equity: Money | None
    realized_pnl: Money
    unrealized_pnl: Money | None
    commissions: Money
    financing: Money
    used_margin: Money | None
    free_margin: Money | None
    stale: bool = Field(strict=True)
    complete: bool = Field(strict=True)


class PortfolioView(Contract):
    kind: Literal["PORTFOLIO"] = "PORTFOLIO"
    account: AccountView
    gross_exposure: Money | None
    open_risk: Money | None
    reserved_risk: Money
    daily_pnl: Money | None
    peak_nav: Money | None
    peak_equity: Money | None = None
    drawdown: Money | None
    risk_state: Literal["ACTIVE", "PAUSE_ENTRIES", "HALT_AND_FLATTEN"] | None
    open_positions: Count
    reserved_positions: Count


class TradeView(Contract):
    episode_id: EntityId
    closed_at: UtcTimestamp
    gross_pnl: Money | None
    net_pnl: Money | None
    net_r: Money | None
    commission: Money | None
    financing: Money | None
    spread_cost: Money | None
    outcome: Literal["WIN", "LOSS", "FLAT", "UNKNOWN"]
    complete: bool = Field(strict=True)


class PositionView(Contract):
    kind: Literal["POSITION"] = "POSITION"
    domain_identity: Label
    episode_id: EntityId
    side: Literal["LONG", "SHORT"]
    quantity: Nonnegative
    average_entry: Price
    mark_price: Price | None
    unrealized_pnl: Money | None
    realized_pnl: Money | None
    stop_loss: Price | None
    take_profit: Price | None
    opened_at: UtcTimestamp
    updated_at: UtcTimestamp
    state: Literal["OPEN", "CLOSED"]
    trade: TradeView | None = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.updated_at < self.opened_at or (self.quantity == 0) != (self.state == "CLOSED"):
            raise ValueError("INVALID_POSITION_LIFECYCLE")
        if self.trade is not None and (
            self.state != "CLOSED"
            or self.trade.episode_id != self.episode_id
            or self.trade.closed_at != self.updated_at
        ):
            raise ValueError("INVALID_COMPLETED_TRADE_LINEAGE")
        return self


class RiskView(Contract):
    kind: Literal["RISK"] = "RISK"
    domain_identity: Label
    policy_id: Label
    risk_state: Literal["ACTIVE", "PAUSE_ENTRIES", "HALT_AND_FLATTEN"]
    risk_per_trade: Money
    open_risk: Money | None
    portfolio_risk_limit: Money
    daily_loss: Money | None
    daily_loss_limit: Money
    drawdown: Money | None
    drawdown_limit: Money
    rejection_reasons: tuple[Label, ...] = ()


class HealthView(Contract):
    kind: Literal["HEALTH"] = "HEALTH"
    component: Literal[
        "database",
        "broker",
        "market_data",
        "risk_engine",
        "portfolio",
        "strategy",
        "ea",
        "reconciliation",
        "system",
    ]
    state: Literal["HEALTHY", "DEGRADED", "STALE", "DISCONNECTED", "ERROR"]
    detail: str = Field(default="", max_length=2000)


class ActivityView(Contract):
    kind: Literal["ACTIVITY"] = "ACTIVITY"
    reference_id: EntityId | None = None
    domain_identity: Label | None = None
    status: Label
    reasons: tuple[Label, ...] = ()
    trades: Count | None = None
    pnl: Money | None = None
    net_r: Money | None = None
    drawdown: Money | None = None


Payload = Annotated[
    AccountView | PortfolioView | PositionView | RiskView | HealthView | ActivityView,
    Field(discriminator="kind"),
]


class EventInput(Contract):
    event_type: EventType
    schema_version: Literal[1] = 1
    scope: Scope
    occurred_at: UtcTimestamp
    recorded_at: UtcTimestamp
    source: Literal["DOMAIN", "EXTERNAL_EA", "ADAPTER", "SYSTEM"]
    source_instance_id: EntityId
    source_sequence: AccountSequence
    strategy_id: EntityId | None = None
    symbol: Asset | None = None
    correlation_id: EntityId
    causation_id: EntityId | None = None
    corrects_event_id: EntityId | None = None
    magic_number: Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)] | None = None
    comment: str | None = Field(default=None, max_length=2000)
    broker_ticket: Label | None = None
    payload: Payload
    read_only: Literal[True] = True

    @field_validator("schema_version", mode="before")
    @classmethod
    def strict_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("INTEGER_SCHEMA_VERSION_REQUIRED")
        return value

    @field_validator("read_only", mode="before")
    @classmethod
    def read_only_required(cls, value: object) -> object:
        if value is not True:
            raise ValueError("READ_ONLY_REQUIRED")
        return value

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.recorded_at < self.occurred_at:
            raise ValueError("RECORDED_BEFORE_OCCURRENCE")
        if self.scope.environment == Environment.LIVE and self.source == "DOMAIN":
            raise ValueError("LIVE_IS_EXTERNAL_OBSERVATION_ONLY")
        name = self.event_type.value
        expected = (
            "ACCOUNT"
            if name == "ACCOUNT_SNAPSHOT"
            else "PORTFOLIO"
            if name == "PORTFOLIO_SNAPSHOT"
            else "POSITION"
            if name.startswith("POSITION_")
            else "RISK"
            if name.startswith("RISK_")
            else "HEALTH"
            if name.startswith(("BROKER_", "RECONCILIATION_"))
            or name in {"EA_HEALTH", "SYSTEM_HEALTH"}
            else "ACTIVITY"
        )
        if self.payload.kind != expected:
            raise ValueError("EVENT_PAYLOAD_KIND_MISMATCH")
        if (
            expected in {"ACCOUNT", "PORTFOLIO", "POSITION", "RISK"}
            and self.scope.account_id is None
        ):
            raise ValueError("ACCOUNT_REQUIRED")
        if isinstance(self.payload, PositionView):
            if self.symbol is None or (self.source == "DOMAIN" and self.strategy_id is None):
                raise ValueError("POSITION_ATTRIBUTION_REQUIRED")
            if self.payload.updated_at != self.occurred_at:
                raise ValueError("POSITION_TIME_MISMATCH")
            if (name == "POSITION_CLOSED") != (self.payload.state == "CLOSED"):
                raise ValueError("POSITION_EVENT_STATE_MISMATCH")
        if isinstance(self.payload, HealthView):
            if name == "EA_HEALTH" and self.payload.component != "ea":
                raise ValueError("EA_HEALTH_COMPONENT_MISMATCH")
            fixed = {
                "BROKER_CONNECTED": ("broker", "HEALTHY"),
                "BROKER_DISCONNECTED": ("broker", "DISCONNECTED"),
                "BROKER_STALE": ("broker", "STALE"),
                "RECONCILIATION_OK": ("reconciliation", "HEALTHY"),
                "RECONCILIATION_MISMATCH": ("reconciliation", "ERROR"),
                "RECONCILIATION_STARTED": ("reconciliation", "DEGRADED"),
            }
            if name in fixed and (self.payload.component, self.payload.state) != fixed[name]:
                raise ValueError("HEALTH_EVENT_STATE_MISMATCH")
        if isinstance(self.payload, RiskView):
            if name == "RISK_APPROVED" and (
                self.payload.risk_state != "ACTIVE" or self.payload.rejection_reasons
            ):
                raise ValueError("INVALID_RISK_APPROVAL")
            if name == "RISK_REJECTED" and not self.payload.rejection_reasons:
                raise ValueError("RISK_REJECTION_REASON_REQUIRED")
        return self

    def expected_id(self) -> UUID:
        return UUID(
            hex=digest(
                canonical_bytes(
                    {
                        "stream": self.scope.stream_id,
                        "source": self.source_instance_id,
                        "sequence": self.source_sequence,
                    }
                )
            )[:32]
        )


class TelemetryEvent(EventInput):
    event_id: EntityId

    @model_validator(mode="after")
    def identity_valid(self) -> Self:
        if self.event_id != self.expected_id():
            raise ValueError("EVENT_IDENTITY_MISMATCH")
        return self


def create_event(value: EventInput) -> TelemetryEvent:
    value = EventInput.model_validate(value.model_dump())
    return TelemetryEvent.model_validate({**value.model_dump(), "event_id": value.expected_id()})


class StoredEvent(Contract):
    sequence: AccountSequence
    event: TelemetryEvent
    previous_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    event_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def verified(self) -> Self:
        if self.event_hash != digest(canonical_bytes(self.model_dump(exclude={"event_hash"}))):
            raise ValueError("TELEMETRY_HASH_MISMATCH")
        return self


def seal(event: TelemetryEvent, sequence: int, previous_hash: str) -> StoredEvent:
    data = {"event": event.model_dump(), "sequence": sequence, "previous_hash": previous_hash}
    return StoredEvent.model_validate({**data, "event_hash": digest(canonical_bytes(data))})
