"""Versioned observation contracts; registry evidence never equates magic with identity."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.domain.primitives import FrozenModel, UtcTimestamp
from trading_ecosystem.mt5.client import Record


def content_id(value: object) -> str:
    return digest(canonical_bytes(value))


class Candidate(FrozenModel):
    ea_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=150)
    vendor: str | None = None
    version: str | None = None
    magic_numbers: tuple[int, ...]
    symbols: tuple[str, ...]
    comment: str | None = None
    source: Literal["INTERNAL_STRATEGY", "EXTERNAL_EA", "MANUAL", "UNKNOWN"] = "EXTERNAL_EA"
    attribution_reference: str | None = None
    exclusive_binding: bool = False
    notes: str = ""
    status: Literal["ACTIVE", "DISABLED"] = "ACTIVE"


class Config(FrozenModel):
    mode: Literal["EXTERNAL_EA_OBSERVATION"] = "EXTERNAL_EA_OBSERVATION"
    symbols: tuple[str, ...]
    candidates: tuple[Candidate, ...] = ()
    poll_ms: int = Field(default=1000, ge=250, le=1000)
    history_seconds: int = Field(default=3, ge=2, le=5)
    overlap_seconds: int = Field(default=120, ge=5, le=3600)
    history_days: int = Field(default=1, ge=1, le=7)
    bars_per_window: int = Field(default=50, ge=50, le=200)
    max_records: int = Field(default=10000, ge=1, le=100000)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if not self.symbols or len(set(self.symbols)) != len(self.symbols):
            raise ValueError("DISTINCT_OBSERVER_SYMBOLS_REQUIRED")
        if len({c.ea_id for c in self.candidates}) != len(self.candidates):
            raise ValueError("DUPLICATE_EA_REGISTRY_ID")
        return self


class ObservationSession(FrozenModel):
    session_id: UUID
    account_scope: UUID
    broker: str
    server_scope: str
    environment: Literal["DEMO"] = "DEMO"
    mode: Literal["EXTERNAL_EA_OBSERVATION"] = "EXTERNAL_EA_OBSERVATION"
    margin_mode: Literal[0, 1, 2]
    started_at: UtcTimestamp
    terminal_build: int
    config: Config
    observer_version: Literal["4B_V1"] = "4B_V1"


class Attribution(FrozenModel):
    source: Literal["INTERNAL_STRATEGY", "EXTERNAL_EA", "MANUAL", "UNKNOWN"] = "UNKNOWN"
    confidence: Literal["KNOWN", "PROBABLE", "AMBIGUOUS", "UNKNOWN"] = "UNKNOWN"
    candidate_id: str | None = None
    matching_candidates: tuple[str, ...] = ()
    evidence_reference: str | None = None


def attribute(row: Record, config: Config) -> Attribution:
    matches = [
        c
        for c in config.candidates
        if c.status == "ACTIVE"
        and row.get("magic") in c.magic_numbers
        and row.get("symbol") in c.symbols
        and (c.comment is None or c.comment == row.get("comment"))
    ]
    if len(matches) > 1:
        return Attribution(
            confidence="AMBIGUOUS", matching_candidates=tuple(sorted(c.ea_id for c in matches))
        )
    if not matches:
        return Attribution()
    c = matches[0]
    known = c.exclusive_binding and bool(c.attribution_reference)
    return Attribution(
        source=c.source if known else "UNKNOWN",
        confidence="KNOWN" if known else "PROBABLE",
        candidate_id=c.ea_id,
        matching_candidates=(c.ea_id,),
        evidence_reference=c.attribution_reference,
    )


class Frame(FrozenModel):
    session_id: UUID
    sequence: int = Field(ge=1)
    observed_at: UtcTimestamp
    recovered: bool = False
    account: Record
    positions: tuple[Record, ...]
    orders: tuple[Record, ...]
    deals: tuple[Record, ...]
    history_orders: tuple[Record, ...] = ()
    quotes: dict[str, Record]
    metadata: dict[str, Record]
    contexts: dict[str, Record] = {}


class LifecycleEvent(FrozenModel):
    event_id: str
    session_id: UUID
    sequence: int
    kind: str
    observed_at: UtcTimestamp
    broker_at: UtcTimestamp | None = None
    quality: Literal["DIRECT", "RECONSTRUCTED", "AMBIGUOUS"]
    recovered_state: bool
    attribution: Attribution
    symbol: str
    position_id: str | None
    values: Record
    raw_reference: str
    context_reference: str | None = None
