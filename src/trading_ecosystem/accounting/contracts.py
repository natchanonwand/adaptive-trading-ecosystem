"""Immutable, validated accounting inputs and authoritative read models."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.domain.primitives import (
    AccountSequence,
    Asset,
    EntityId,
    FrozenModel,
    Money,
    Price,
    Quantity,
    UtcTimestamp,
)

Count = Annotated[int, Field(strict=True, ge=0)]
Nonnegative = Annotated[Money, Field(ge=0)]
Label = Annotated[str, Field(min_length=1, max_length=128)]


class Contract(FrozenModel):
    model_config = ConfigDict(revalidate_instances="always")

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        return type(self).model_validate({**self.model_dump(), **(update or {})})

    @classmethod
    def model_construct(  # type: ignore[override]
        cls, _fields_set: set[str] | None = None, **values: Any
    ) -> Self:
        raise TypeError("UNCHECKED_ACCOUNTING_CONSTRUCTION_FORBIDDEN")

    @property
    def identity(self) -> str:
        return digest(canonical_bytes({"contract": type(self).__name__, "data": self.model_dump()}))


class Category(StrEnum):
    CASH_FLOW = "CASH_FLOW"
    REALIZED_PNL = "REALIZED_PNL"
    COMMISSION = "COMMISSION"
    FINANCING = "FINANCING"
    ADJUSTMENT = "ADJUSTMENT"


class LedgerEntry(Contract):
    entry_id: EntityId
    account_id: EntityId
    sequence: AccountSequence
    currency: Literal["USD"] = "USD"
    amount: Money
    category: Category
    reference_id: EntityId
    effective_at: UtcTimestamp
    recorded_at: UtcTimestamp
    reverses: EntityId | None = None
    replaces: EntityId | None = None
    audit_reference: Label | None = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.recorded_at < self.effective_at:
            raise ValueError("RECORDED_BEFORE_EFFECTIVE")
        if self.reverses is not None and self.replaces is not None:
            raise ValueError("SEPARATE_REVERSAL_AND_REPLACEMENT_REQUIRED")
        if (self.category == Category.ADJUSTMENT or self.reverses or self.replaces) and not (
            self.audit_reference
        ):
            raise ValueError("AUDIT_REFERENCE_REQUIRED")
        return self


class UsdValuationModel(Contract):
    """Explicit linear contract; factor is USD / (quantity unit * price unit).

    A later adapter must validate this model against broker examples. No default
    factor or implicit instrument economics are supplied by accounting.
    """

    model_id: Label
    model_version: Literal["LINEAR_USD_FACTOR_V1"] = "LINEAR_USD_FACTOR_V1"
    instrument_id: Label
    asset: Asset
    currency: Literal["USD"] = "USD"
    quantity_unit: Label
    price_unit: Label
    usd_per_quantity_price_unit: Price
    valid_from: UtcTimestamp
    valid_until: UtcTimestamp
    validation_reference: Label | None = None

    @model_validator(mode="after")
    def interval(self) -> Self:
        if self.valid_until <= self.valid_from:
            raise ValueError("INVALID_VALUATION_INTERVAL")
        return self


class LongPosition(Contract):
    episode_id: EntityId
    asset: Asset
    instrument_id: Label
    direction: Literal["LONG"] = "LONG"
    quantity: Quantity
    quantity_unit: Label
    price_unit: Label
    weighted_actual_entry: Price
    current_bid: Price | None
    quote_id: Label | None
    quote_at: UtcTimestamp | None
    reconciled_sequence: Count
    valuation_model: UsdValuationModel | None

    @model_validator(mode="after")
    def quote_shape(self) -> Self:
        fields = (self.current_bid, self.quote_id, self.quote_at)
        if any(value is None for value in fields) and not all(value is None for value in fields):
            raise ValueError("PARTIAL_QUOTE_METADATA")
        return self


class Reservation(Contract):
    episode_id: EntityId
    asset: Asset


class AccountInput(Contract):
    account_id: EntityId
    currency: Literal["USD"] = "USD"
    opening_at: UtcTimestamp
    opening_cash: Money
    valuation_at: UtcTimestamp
    reconciled_at: UtcTimestamp
    ledger: tuple[LedgerEntry, ...] = ()
    positions: tuple[LongPosition, ...] = ()
    reservations: tuple[Reservation, ...] = ()
    used_margin: Nonnegative | None = None
    reserved_margin: Nonnegative | None = None
    open_stop_risk: Nonnegative | None = None
    reserved_stop_risk: Nonnegative | None = None

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not self.opening_at <= self.reconciled_at <= self.valuation_at:
            raise ValueError("INVALID_ACCOUNT_CHRONOLOGY")
        entries: dict[UUID, LedgerEntry] = {}
        reversed_ids = set()
        replaced_ids = set()
        previous_time = self.opening_at
        previous_recorded = self.opening_at
        for sequence, entry in enumerate(self.ledger, 1):
            if entry.entry_id in entries:
                raise ValueError("DUPLICATE_LEDGER_IDENTITY")
            if entry.sequence != sequence or entry.account_id != self.account_id:
                raise ValueError("ACCOUNT_OR_CONTIGUOUS_SEQUENCE_MISMATCH")
            if not previous_time <= entry.effective_at <= entry.recorded_at <= self.reconciled_at:
                raise ValueError("INVALID_LEDGER_CHRONOLOGY")
            if entry.recorded_at < previous_recorded:
                raise ValueError("REVERSED_RECORDING_ORDER")
            target_id = entry.reverses or entry.replaces
            if target_id is not None:
                target = entries.get(target_id)
                if target is None or target.reverses or target.replaces:
                    raise ValueError("CORRECTION_REQUIRES_ORIGINAL_PRIOR_ENTRY")
                if entry.category != target.category or entry.reference_id != target.reference_id:
                    raise ValueError("CORRECTION_LINEAGE_MISMATCH")
                if entry.reverses:
                    if target_id in reversed_ids or entry.amount != target.amount.copy_negate():
                        raise ValueError("INVALID_REVERSAL")
                    reversed_ids.add(target_id)
                else:
                    if target_id not in reversed_ids or target_id in replaced_ids:
                        raise ValueError("REPLACEMENT_REQUIRES_SINGLE_PRIOR_REVERSAL")
                    replaced_ids.add(target_id)
            entries[entry.entry_id] = entry
            previous_time, previous_recorded = entry.effective_at, entry.recorded_at
        positions = sorted(self.positions, key=lambda item: item.asset.value)
        reservations = sorted(self.reservations, key=lambda item: item.asset.value)
        if list(self.positions) != positions or list(self.reservations) != reservations:
            raise ValueError("LEXICAL_ASSET_ORDER_REQUIRED")
        occupied: tuple[LongPosition | Reservation, ...] = (*self.positions, *self.reservations)
        if len({item.asset for item in occupied}) != len(occupied):
            raise ValueError("ONE_OPEN_OR_PENDING_EPISODE_PER_ASSET")
        if len({item.episode_id for item in occupied}) != len(occupied):
            raise ValueError("DUPLICATE_EPISODE_IDENTITY")
        for position in self.positions:
            if position.reconciled_sequence != len(self.ledger):
                raise ValueError("POSITION_LEDGER_BOUNDARY_MISMATCH")
            if position.quote_at is not None and position.quote_at > self.valuation_at:
                raise ValueError("FUTURE_QUOTE")
        return self


class Balance(Contract):
    opening_cash: Money
    external_cash_flows: Money
    realized_pnl: Money
    commissions: Money
    financing: Money
    audited_adjustments: Money
    cash_balance: Money


class AssetValuation(Contract):
    asset: Asset
    position: LongPosition | None
    reserved_episode: EntityId | None
    unrealized_pnl: Money | None
    stale: bool
    unavailable_reason: str | None


class EquitySnapshot(Contract):
    phase: Literal["PHASE3_4A_ACCOUNTING_ONLY"] = "PHASE3_4A_ACCOUNTING_ONLY"
    qualification_eligible: Literal[False] = False
    arithmetic_version: Literal["decimal34-half-even-v1"] = "decimal34-half-even-v1"
    source: AccountInput
    ledger_sequence: Count
    balance: Balance
    assets: tuple[AssetValuation, ...]
    unrealized_pnl: Money | None
    equity: Money | None
    complete: bool
    stale: bool
    open_episode_count: Count
    reserved_episode_count: Count


class NavState(Contract):
    units: Money | None
    nav: Money | None
    high_water_mark: Money | None
    drawdown: Money | None
    drawdown_triggered: bool | None
    unavailable_reason: str | None


class RiskDayState(Contract):
    boundary_at: UtcTimestamp
    boundary_snapshot_id: str | None
    boundary_equity: Money | None
    net_external_flows: Money | None
    today_trading_pnl: Money | None
    daily_loss_fraction: Money | None
    daily_loss_triggered: bool | None
    unavailable_reason: str | None


class PortfolioSnapshot(Contract):
    equity_snapshot: EquitySnapshot
    history_id: str
    nav: NavState
    risk_day: RiskDayState
    accounting_entry_eligible: bool
    qualification_eligible: Literal[False] = False
