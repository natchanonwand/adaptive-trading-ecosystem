"""One immutable configuration per run; unknown observations stay explicit."""

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from trading_ecosystem.domain.primitives import FrozenModel, UtcTimestamp


class State(StrEnum):
    NOT_READY = "NOT_READY"
    READY = "READY"
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    PARSING = "PARSING"
    COMPLETE = "COMPLETE"
    BLOCKED_LICENSE = "BLOCKED_LICENSE"
    BLOCKED_TESTER_ACCESS = "BLOCKED_TESTER_ACCESS"
    BLOCKED_SYMBOL = "BLOCKED_SYMBOL"
    BLOCKED_ARTIFACT_IDENTITY_MISMATCH = "BLOCKED_ARTIFACT_IDENTITY_MISMATCH"
    BLOCKED_REAL_TICKS_UNAVAILABLE = "BLOCKED_REAL_TICKS_UNAVAILABLE"
    INITIALIZATION_FAILED = "INITIALIZATION_FAILED"
    TESTER_FAILED = "TESTER_FAILED"
    TIMEOUT = "TIMEOUT"
    REPORT_MISSING = "REPORT_MISSING"
    REPORT_PARSE_FAILED = "REPORT_PARSE_FAILED"
    CANCELLED = "CANCELLED"


ACTIVE = {State.QUEUED, State.PREPARING, State.RUNNING, State.PARSING}
FAILURES = set(State) - ACTIVE - {State.NOT_READY, State.READY, State.COMPLETE}


def transition(current: State, target: State) -> State:
    next_steps = {
        State.READY: {State.QUEUED, State.CANCELLED},
        State.QUEUED: {State.PREPARING} | FAILURES,
        State.PREPARING: {State.RUNNING} | FAILURES,
        State.RUNNING: {State.PARSING} | FAILURES,
        State.PARSING: {State.COMPLETE} | FAILURES,
    }
    if target not in next_steps.get(current, set()):
        raise ValueError("INVALID_BASELINE_TRANSITION")
    return target


class Configuration(FrozenModel):
    baseline_run_id: UUID
    project_id: UUID
    environment: Literal["DEMO_RESEARCH_TESTER"] = "DEMO_RESEARCH_TESTER"
    symbol: Literal["XAUUSDm", "BTCUSDm", "USTECm"]
    timeframe: Literal["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
    tester_model: Literal["EVERY_TICK_BASED_ON_REAL_TICKS"] = "EVERY_TICK_BASED_ON_REAL_TICKS"
    from_date: date
    to_date: date
    initial_deposit: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    currency: Literal["USD"] = "USD"
    leverage: int = Field(ge=1, le=2000, strict=True)
    timeout_seconds: int = Field(default=600, ge=30, le=3600, strict=True)
    input_provenance: Literal["TESTER_DEFAULTS", "USER_SET"] = "TESTER_DEFAULTS"
    set_text: str | None = Field(default=None, max_length=65536)

    @model_validator(mode="after")
    def bounded(self) -> "Configuration":
        if not date(2000, 1, 1) <= self.from_date < self.to_date <= datetime.now(UTC).date():
            raise ValueError("INVALID_HISTORICAL_INTERVAL")
        if (self.to_date - self.from_date).days > 366:
            raise ValueError("BASELINE_INTERVAL_LIMIT_366_DAYS")
        if (self.input_provenance == "USER_SET") != (self.set_text is not None):
            raise ValueError("EXPLICIT_INPUT_PROVENANCE_REQUIRED")
        if self.set_text is not None:
            from trading_ecosystem.tester.inputs import validate_set

            validate_set(self.set_text)
        return self


class Run(FrozenModel):
    config: Configuration
    candidate_id: UUID
    artifact_id: UUID
    ea_sha256: str
    input_sha256: str | None
    declared_license_status: str
    declared_tester_access: str
    observed_tester_status: Literal[
        "UNKNOWN", "SUCCESS", "LICENSE_BLOCKED", "INITIALIZATION_FAILED"
    ] = "UNKNOWN"
    status: State = State.READY
    history: tuple[State, ...] = (State.READY,)
    created_at: UtcTimestamp
    started_at: UtcTimestamp | None = None
    completed_at: UtcTimestamp | None = None
    exit_code: int | None = None
    terminal_build: str = "UNKNOWN"
    result_identity: str | None = None
    evidence_identity: str | None = None
    diagnostic: str = "READY_FOR_EXPLICIT_START"


class Result(FrozenModel):
    baseline_run_id: UUID
    project_id: UUID
    candidate_id: UUID
    metrics: dict[str, str | int | None]
    unavailable: tuple[str, ...]
    metadata: dict[str, str]
    report_identity: str
    result_identity: str
