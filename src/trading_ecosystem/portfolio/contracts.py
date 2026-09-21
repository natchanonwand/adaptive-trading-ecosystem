"""Explicit USD economics, reconciled fills, positions and reservations."""

from typing import Literal, Self

from pydantic import Field, model_validator

from trading_ecosystem.accounting.contracts import AccountInput, Contract, Label, Nonnegative
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import (
    Asset,
    EntityId,
    Money,
    Price,
    Quantity,
    UtcTimestamp,
)

Direction = Literal["LONG", "SHORT"]


class Economics(Contract):
    instrument_id: Label
    asset: Asset
    version: Label
    account_currency: Literal["USD"] = "USD"
    quote_currency: Literal["USD"] = "USD"
    quantity_unit: Literal["LOT"] = "LOT"
    price_unit: Literal["USD_PER_CONTRACT_UNIT"] = "USD_PER_CONTRACT_UNIT"
    model: Literal["LINEAR_USD_V1"] = "LINEAR_USD_V1"
    tick_size: Price
    tick_value_per_lot: Price
    contract_size: Price
    usd_per_price_unit_per_lot: Price
    volume_min: Quantity
    volume_max: Quantity
    volume_step: Quantity
    margin_per_lot: Nonnegative
    commission_per_lot_per_side: Nonnegative
    commission_fixed_per_side: Nonnegative
    minimum_stop_distance: Nonnegative
    valid_from: UtcTimestamp
    valid_until: UtcTimestamp
    validation_reference: Label | None

    @model_validator(mode="after")
    def valid(self) -> Self:
        with arithmetic_context():
            if self.tick_value_per_lot != self.tick_size * self.usd_per_price_unit_per_lot:
                raise ValueError("INCONSISTENT_TICK_VALUE")
        if self.volume_max < self.volume_min or self.valid_until <= self.valid_from:
            raise ValueError("INVALID_ECONOMICS_RANGE")
        return self


class Quote(Contract):
    quote_id: Label
    instrument_id: Label
    at: UtcTimestamp
    bid: Price
    ask: Price

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.ask < self.bid:
            raise ValueError("CROSSED_QUOTE")
        return self


class Position(Contract):
    episode_id: EntityId
    strategy_id: EntityId
    asset: Asset
    direction: Direction
    economics: Economics
    quantity: Quantity
    weighted_entry: Price
    fixed_stop: Price
    reducing: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.asset != self.economics.asset:
            raise ValueError("POSITION_INSTRUMENT_MISMATCH")
        return self


class Fill(Contract):
    fill_id: EntityId
    realized_entry_id: EntityId
    commission_entry_id: EntityId
    account_id: EntityId
    episode_id: EntityId
    strategy_id: EntityId
    asset: Asset
    direction: Direction
    action: Literal["INCREASE", "REDUCE"]
    side: Literal["BUY", "SELL"]
    quantity: Quantity
    actual_price: Price
    fixed_stop: Price
    actual_commission: Money
    at: UtcTimestamp
    economics: Economics

    @model_validator(mode="after")
    def valid(self) -> Self:
        buy = (self.direction == "LONG") == (self.action == "INCREASE")
        if self.side != ("BUY" if buy else "SELL") or self.asset != self.economics.asset:
            raise ValueError("FILL_SIDE_OR_ASSET_MISMATCH")
        if len({self.fill_id, self.realized_entry_id, self.commission_entry_id}) != 3:
            raise ValueError("DISTINCT_FILL_AND_POSTING_IDENTITIES_REQUIRED")
        return self


class FillReceipt(Contract):
    fill_id: EntityId
    content_id: Label


class Book(Contract):
    cash: AccountInput
    positions: tuple[Position, ...] = ()
    receipts: tuple[FillReceipt, ...] = ()
    closed_episodes: tuple[EntityId, ...] = ()

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.cash.positions or self.cash.reservations:
            raise ValueError("BOOK_OWNS_POSITION_AND_RESERVATION_PROJECTION")
        if len({p.episode_id for p in self.positions}) != len(self.positions):
            raise ValueError("DUPLICATE_EPISODE")
        if len({p.fill_id for p in self.receipts}) != len(self.receipts):
            raise ValueError("DUPLICATE_FILL_RECEIPT")
        if any(p.episode_id in self.closed_episodes for p in self.positions):
            raise ValueError("CLOSED_EPISODE_REOPENED")
        return self


class Reservation(Contract):
    reservation_id: Label
    intent_id: EntityId
    strategy_id: EntityId
    asset: Asset
    direction: Direction
    volume: Quantity
    stop_risk: Nonnegative
    gross_notional: Nonnegative
    margin: Nonnegative
    decision_id: Label


class Observation(Contract):
    book: Book
    quotes: tuple[Quote, ...] = ()
    reservations: tuple[Reservation, ...] = ()

    @model_validator(mode="after")
    def valid(self) -> Self:
        if len({q.instrument_id for q in self.quotes}) != len(self.quotes):
            raise ValueError("DUPLICATE_INSTRUMENT_QUOTE")
        if any(q.at > self.book.cash.valuation_at for q in self.quotes):
            raise ValueError("FUTURE_MARK")
        if len({r.reservation_id for r in self.reservations}) != len(self.reservations):
            raise ValueError("DUPLICATE_RESERVATION")
        if len({r.intent_id for r in self.reservations}) != len(self.reservations):
            raise ValueError("DUPLICATE_RESERVED_INTENT")
        return self
