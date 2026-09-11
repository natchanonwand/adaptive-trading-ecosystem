"""Versioned, immutable Phase 2B contracts."""

from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from types import MappingProxyType
from typing import Annotated, Final, Literal, Self

from pydantic import BeforeValidator, Field, model_validator

from trading_ecosystem.domain.primitives import Asset, FrozenModel, finite_decimal

MAPPINGS = MappingProxyType({"BTCUSD": "BTCUSDm", "XAUUSD": "XAUUSDm", "USTEC100": "USTECm"})
PRICE_BASIS: Final = "MT5_CHART_BAR_BASIS_UNVERIFIED"
AVAILABILITY_BASIS: Final = "MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH"
SCHEMA_VERSION: Final = "phase2b-h1-v1"
ARITHMETIC_VERSION: Final = "decimal34-scale18-v1"
HOUR = timedelta(hours=1)


def strict_utc(value: object) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    if value.utcoffset() != timedelta(0):
        raise ValueError("NON_UTC_TIMESTAMP")
    return value


def exact_price(value: object) -> Decimal:
    result = finite_decimal(value)
    if result <= 0:
        raise ValueError("NONPOSITIVE_PRICE")
    with localcontext() as ctx:
        ctx.prec = 140
        scaled = result * Decimal(10) ** 18
        if scaled != scaled.to_integral_value() or scaled >= Decimal(10) ** 34:
            raise ValueError("DECIMAL_NOT_EXACTLY_REPRESENTABLE")
    return result


Timestamp = Annotated[datetime, BeforeValidator(strict_utc)]
Financial = Annotated[Decimal, BeforeValidator(exact_price)]
Count = Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Window(FrozenModel):
    requested_start: Timestamp
    requested_end: Timestamp

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if self.requested_start >= self.requested_end:
            raise ValueError("EMPTY_OR_REVERSED_WINDOW")
        for value in (self.requested_start, self.requested_end):
            if value.minute or value.second or value.microsecond:
                raise ValueError("H1_ALIGNMENT")
        return self


class Bar(FrozenModel):
    dataset_id: str
    canonical_asset: Asset
    broker_symbol: str
    instrument_metadata_reference: Hash
    instrument_metadata_temporal_scope: Literal["CURRENT_SNAPSHOT_ONLY"] = "CURRENT_SNAPSHOT_ONLY"
    timeframe: Literal["H1"] = "H1"
    open_time: Timestamp
    close_time: Timestamp
    available_at: Timestamp
    availability_basis: Literal["MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH"] = (
        AVAILABILITY_BASIS
    )
    open: Financial
    high: Financial
    low: Financial
    close: Financial
    tick_volume: Count
    spread_points: Count
    real_volume: Count
    price_basis: Literal["MT5_CHART_BAR_BASIS_UNVERIFIED"] = PRICE_BASIS
    source: Literal["MetaTrader5"] = "MetaTrader5"
    source_version: str | None = None
    retrieved_at: Timestamp
    quality_flags: tuple[Literal["EXPLORATORY_RESEARCH_ONLY"], ...] = ("EXPLORATORY_RESEARCH_ONLY",)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if MAPPINGS[self.canonical_asset] != self.broker_symbol:
            raise ValueError("SYMBOL_MISMATCH")
        if self.open_time.minute or self.open_time.second or self.open_time.microsecond:
            raise ValueError("H1_ALIGNMENT")
        if self.close_time != self.open_time + HOUR or self.available_at != self.close_time:
            raise ValueError("BAR_CLOSE_AVAILABILITY")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("INVALID_OHLC")
        return self


class Chunk(Window):
    canonical_asset: Asset
    broker_symbol: str
    retrieved_at: Timestamp
    row_count: Count
    first_bar: Timestamp | None
    last_bar: Timestamp | None
    status: Literal["OBSERVED", "EMPTY", "ERROR"]
    error: str | None
    source_file: str
    source_hash: Hash


class Gap(FrozenModel):
    classification: Literal["UNCLASSIFIED_GAP"] = "UNCLASSIFIED_GAP"
    gap_start: Timestamp
    gap_end: Timestamp
    missing_clock_hours: Count
    previous_bar: Timestamp | None
    next_bar: Timestamp | None


class QuarantinedObservation(Window):
    classification: Literal["OUTSIDE_REQUESTED_CHUNK"] = "OUTSIDE_REQUESTED_CHUNK"
    source_file: str
    row_index: Count
    observed_time: Timestamp


class Quality(FrozenModel):
    validation_status: Literal["PASS", "FAIL"]
    bar_count: Count
    duplicate_count: Count
    conflicting_duplicate_count: Count
    invalid_ohlc_count: Count
    invalid_record_count: Count
    failed_chunk_count: Count
    issues: tuple[str, ...]
    gaps: tuple[Gap, ...]
    missing_clock_hours: Count
    largest_gap: Count
    outside_chunk_observation_count: Count = 0
    quarantined_observations: tuple[QuarantinedObservation, ...] = ()


class Manifest(Window):
    dataset_id: str
    manifest_version: Literal["phase2b-manifest-v1"] = "phase2b-manifest-v1"
    canonical_asset: Asset
    broker_symbol: str
    broker_company: Literal["Exness Technologies Ltd"] = "Exness Technologies Ltd"
    server: Literal["Exness-MT5Trial14"] = "Exness-MT5Trial14"
    actual_start: Timestamp | None
    actual_end: Timestamp | None
    timeframe: Literal["H1"] = "H1"
    classification: Literal["EXPLORATORY_RESEARCH_ONLY"] = "EXPLORATORY_RESEARCH_ONLY"
    price_basis: Literal["MT5_CHART_BAR_BASIS_UNVERIFIED"] = PRICE_BASIS
    availability_basis: Literal["MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH"] = (
        AVAILABILITY_BASIS
    )
    qualification_eligible: Literal[False] = False
    instrument_metadata_temporal_scope: Literal["CURRENT_SNAPSHOT_ONLY"] = "CURRENT_SNAPSHOT_ONLY"
    provider_snapshot_hash: Hash
    metadata_snapshot_hash: Hash
    normalized_parquet_hash: Hash
    quality_hash: Hash
    chunks: tuple[Chunk, ...]
    schema_version: Literal["phase2b-h1-v1"] = SCHEMA_VERSION
    arithmetic_version: Literal["decimal34-scale18-v1"] = ARITHMETIC_VERSION
    code_hash: Hash
    bar_count: Count
    validation_status: Literal["PASS"] = "PASS"
    gap_count: Count
    known_assumptions: tuple[str, ...] = (
        "Availability is modeled at close, not observed historical latency.",
        "SDK doubles converted once via decimal text; original vendor precision unavailable.",
    )
    known_limitations: tuple[str, ...] = (
        "Chart price basis unverified; current metadata not historically effective.",
        "No approved session calendar; all clock-time gaps unclassified, including edges.",
        "Partial provider coverage is preserved; no fills, repairs or synthetic bars.",
    )
    unresolved_items: tuple[str, ...] = (
        "D01: historical units, valuation, margin, costs and protection semantics unvalidated.",
        "D02: licensing, Bid basis, latency, calendars, historical costs and metadata unresolved.",
    )
    manifest_hash: Hash
