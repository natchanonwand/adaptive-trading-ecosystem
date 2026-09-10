"""Provider-neutral immutable discovery observations, not qualified datasets."""

from collections.abc import Iterator
from datetime import datetime
from typing import Literal, Protocol

from pydantic import Field, computed_field

from trading_ecosystem.domain.primitives import Asset, FrozenModel, Money, Price, UtcTimestamp


class DiscoveryError(RuntimeError):
    """Messages contain fixed failure codes only, never native diagnostics."""


class DemoRequired(DiscoveryError):
    pass


class ProviderIdentity(FrozenModel):
    provider: Literal["MetaTrader5"] = "MetaTrader5"
    company: str | None
    server: str | None
    account_currency: str | None
    account_trade_mode: Literal["DEMO"] = "DEMO"
    retrieved_at: UtcTimestamp
    terminal_maxbars: int | None = None
    terminal_connected: bool


class AccountEnvironment(FrozenModel):
    trade_mode: Literal["DEMO"] = "DEMO"
    retrieved_at: UtcTimestamp


class Instrument(FrozenModel):
    broker_symbol: str
    description: str | None
    path: str | None
    currency_base: str | None
    currency_profit: str | None
    currency_margin: str | None


class SymbolCandidate(Instrument):
    canonical_asset: Asset
    status: Literal["BLOCKED"] = "BLOCKED"
    match_basis: Literal["EXACT_NAME", "SEARCH_CANDIDATE"]
    reason: Literal["OWNER_APPROVAL_REQUIRED", "AMBIGUOUS_OWNER_APPROVAL_REQUIRED"]


class NumericMetadata(FrozenModel):
    field: str
    value: Money | None


class IntegerMetadata(FrozenModel):
    field: str
    value: int | None


class InstrumentMetadata(Instrument):
    retrieved_at: UtcTimestamp
    numeric: tuple[NumericMetadata, ...]
    integer: tuple[IntegerMetadata, ...]
    missing_or_invalid_fields: tuple[str, ...]
    historical_validity: Literal["CURRENT_SNAPSHOT_ONLY"] = "CURRENT_SNAPSHOT_ONLY"


class QuoteObservation(FrozenModel):
    broker_symbol: str
    time: UtcTimestamp
    retrieved_at: UtcTimestamp
    bid: Price
    ask: Price
    time_precision: Literal["MILLISECOND", "SECOND"]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def crossed(self) -> bool:
        return self.ask < self.bid


class BarObservation(FrozenModel):
    time: UtcTimestamp
    open: Money | None
    high: Money | None
    low: Money | None
    close: Money | None

    @property
    def valid_ohlc(self) -> bool:
        o, h, low, c = self.open, self.high, self.low, self.close
        return (
            o is not None
            and h is not None
            and low is not None
            and c is not None
            and min(o, h, low, c) > 0
            and low <= min(o, c) <= max(o, c) <= h
        )


class TickObservation(FrozenModel):
    time: UtcTimestamp
    bid: Money | None
    ask: Money | None
    time_precision: Literal["MILLISECOND", "SECOND"]


class BarBatch(FrozenModel):
    rows: tuple[BarObservation, ...]
    malformed_time_count: int = 0
    error: Literal["SDK_EMPTY_OR_UNAVAILABLE"] | None = None


class TickBatch(FrozenModel):
    rows: tuple[TickObservation, ...]
    malformed_time_count: int = 0
    truncated: bool = False
    error: Literal["SDK_EMPTY_OR_UNAVAILABLE"] | None = None


class ProbeInterval(FrozenModel):
    label: str
    requested_start: UtcTimestamp
    requested_end: UtcTimestamp


class BarCoverage(ProbeInterval):
    broker_symbol: str
    retrieved_at: UtcTimestamp
    timeframe: Literal["H1"] = "H1"
    status: Literal["OBSERVED", "EMPTY", "ERROR"]
    actual_earliest: UtcTimestamp | None
    actual_latest: UtcTimestamp | None
    row_count: int
    duplicate_count: int
    invalid_OHLC_count: int
    malformed_time_count: int
    calendar_qualified: Literal[False] = False
    price_basis: Literal["UNVERIFIED_BROKER_OHLC"] = "UNVERIFIED_BROKER_OHLC"


class TickCoverage(ProbeInterval):
    broker_symbol: str
    retrieved_at: UtcTimestamp
    status: Literal["OBSERVED", "EMPTY", "ERROR", "BUDGET_LIMIT"]
    first_available_tick: UtcTimestamp | None
    last_available_tick: UtcTimestamp | None
    tick_count: int
    bid_present: bool | None
    ask_present: bool | None
    crossed_quote_count: int
    malformed_quote_count: int
    malformed_time_count: int
    duplicate_timestamp_count: int
    duplicate_timestamp_groups: int
    max_ticks_per_timestamp: int
    millisecond_timestamp_count: int
    processed_until: UtcTimestamp
    requested_interval_fully_queried: bool
    source_sequence_information: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    continuous_coverage_established: Literal[False] = False
    retrieval_order_is_source_sequence: Literal[False] = False
    query_count: int


class DiscoveryPlan(FrozenModel):
    as_of: UtcTimestamp
    max_ticks_per_probe: int = Field(default=100_000, ge=1, le=100_000)
    max_ticks_total: int = Field(default=2_000_000, ge=1, le=2_000_000)
    max_candidates_per_asset: int = Field(default=3, ge=1, le=3)


class ReadOnlyMarketDataProvider(Protocol):
    def get_provider_identity(self) -> ProviderIdentity: ...
    def get_account_environment(self) -> AccountEnvironment: ...
    def list_instruments(self) -> tuple[Instrument, ...]: ...
    def get_instrument_metadata(self, symbol: str) -> InstrumentMetadata: ...
    def get_latest_quote(self, symbol: str) -> QuoteObservation: ...
    def get_bars(self, symbol: str, start: datetime, end: datetime) -> BarBatch: ...
    def get_ticks(self, symbol: str, start: datetime, end: datetime) -> TickBatch: ...
    def probe_history_coverage(
        self, symbol: str, plan: DiscoveryPlan
    ) -> Iterator[BarCoverage | TickCoverage]: ...
