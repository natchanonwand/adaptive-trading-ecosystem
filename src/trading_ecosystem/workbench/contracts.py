"""Stable onboarding identities, explicit unknowns and bounded readiness states."""

import re
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, Field

from trading_ecosystem.domain.primitives import FrozenModel, UtcTimestamp


def safe_text(value: str) -> str:
    value = value.strip() or "UNKNOWN"
    if re.search(r"(?i)(password|passwd|api[_ -]?key|access[_ -]?token|secret)\s*[:=]", value):
        raise ValueError("CREDENTIALS_NOT_ACCEPTED")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError("INVALID_TEXT")
    return value


Text = Annotated[str, Field(max_length=2000), AfterValidator(safe_text)]


def project_name(value: str) -> str:
    if not value.strip():
        raise ValueError("PROJECT_NAME_REQUIRED")
    return safe_text(value)


class SourceType(StrEnum):
    EXTERNAL_EA = "EXTERNAL_EA"
    STRATEGY_IDEA = "STRATEGY_IDEA"
    QUANT_FORMULA = "QUANT_FORMULA"
    MANUAL_TRADING = "MANUAL_TRADING"


class Status(StrEnum):
    DRAFT = "DRAFT"
    CANDIDATE_REGISTERED = "CANDIDATE_REGISTERED"
    BASELINE_READY = "BASELINE_READY"
    BASELINE_RUNNING = "BASELINE_RUNNING"
    BASELINE_COMPLETE = "BASELINE_COMPLETE"
    TUNING_READY = "TUNING_READY"
    BEHAVIOR_READY = "BEHAVIOR_READY"
    FORWARD_READY = "FORWARD_READY"
    BLOCKED_LICENSE = "BLOCKED_LICENSE"
    BLOCKED_SYMBOL = "BLOCKED_SYMBOL"
    BLOCKED_TESTER = "BLOCKED_TESTER"
    BLOCKED_ATTRIBUTION = "BLOCKED_ATTRIBUTION"
    FAILED_BASELINE = "FAILED_BASELINE"


MAPPINGS = {"BTCUSD": "BTCUSDm", "XAUUSD": "XAUUSDm", "USTEC100": "USTECm", "US100": "USTECm"}
CATALOG = [
    dict(
        catalog_id="gold-scalper",
        product_name="Gold Scalper for MT5 EA",
        asset="XAUUSD",
        research_class="transparent/simple pilot",
        source_reference="UNKNOWN",
    ),
    dict(
        catalog_id="btc-autotrader",
        product_name="BTC AutoTrader",
        asset="BTCUSD",
        research_class="breakout/pending pilot",
        source_reference="UNKNOWN",
    ),
    dict(
        catalog_id="artemis-orb",
        product_name="Artemis NAS100 ORB Edge",
        asset="US100",
        research_class="ORB/index pilot",
        source_reference="UNKNOWN",
    ),
]


class Binding(FrozenModel):
    broker_name: Text = "UNKNOWN"
    environment: Literal["DEMO"] = "DEMO"
    canonical_asset: Literal["BTCUSD", "XAUUSD", "USTEC100", "US100", "UNKNOWN"] = "UNKNOWN"
    broker_symbol: Text = "UNKNOWN"
    timeframe: Literal["M1", "M5", "M15", "M30", "H1", "H4", "D1", "UNKNOWN"] = "UNKNOWN"
    symbol_confirmed: bool = False

    def ready(self) -> bool:
        return bool(
            self.symbol_confirmed
            and self.broker_name != "UNKNOWN"
            and self.timeframe != "UNKNOWN"
            and MAPPINGS.get(self.canonical_asset) == self.broker_symbol
        )


class CandidateInput(FrozenModel):
    product_name: Text = "UNKNOWN"
    version: Text = "UNKNOWN"
    vendor: Text = "UNKNOWN"
    source_reference: Text = "UNKNOWN"
    catalog_id: str | None = None
    artifact_id: UUID | None = None
    manual_id: UUID | None = None
    license_status: Literal["UNKNOWN", "USER_ATTESTED", "NOT_AUTHORIZED"] = "UNKNOWN"
    tester_access_status: Literal["UNKNOWN", "USER_CONFIRMED", "UNAVAILABLE"] = "UNKNOWN"
    known_magic_number: int | None = Field(default=None, strict=True, ge=0, le=2**53 - 1)
    known_order_comments: Text = "UNKNOWN"
    notes: Text = "UNKNOWN"


class CreateProject(FrozenModel):
    # Client-generated request identity makes double clicks/retries idempotent.
    project_id: UUID
    project_name: Annotated[str, Field(min_length=1, max_length=150), AfterValidator(project_name)]
    source_type: SourceType
    candidate: CandidateInput
    broker_binding: Binding


class Artifact(FrozenModel):
    artifact_id: UUID
    role: Literal["EA", "MANUAL"]
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(gt=0, le=16 * 1024 * 1024)
    uploaded_at: UtcTimestamp


class Candidate(CandidateInput):
    candidate_id: UUID
    artifact_filename: str = "UNKNOWN"
    artifact_sha256: str | None = None
    artifact_size: int | None = None
    manual_filename: str = "UNKNOWN"
    manual_sha256: str | None = None
    manual_size: int | None = None
    expected_asset: str
    expected_symbol: str
    expected_timeframe: str


class Project(FrozenModel):
    project_id: UUID
    project_name: str
    source_type: SourceType
    candidate_id: UUID
    broker_binding: Binding
    status: Status
    status_history: tuple[Status, ...]
    created_at: UtcTimestamp
    updated_at: UtcTimestamp


def transition(current: Status, target: Status) -> Status:
    allowed = {
        Status.DRAFT: {Status.CANDIDATE_REGISTERED},
        Status.CANDIDATE_REGISTERED: {
            Status.BASELINE_READY,
            Status.BLOCKED_LICENSE,
            Status.BLOCKED_SYMBOL,
            Status.BLOCKED_TESTER,
            Status.BLOCKED_ATTRIBUTION,
        },
        Status.BLOCKED_LICENSE: {Status.CANDIDATE_REGISTERED},
        Status.BLOCKED_SYMBOL: {Status.CANDIDATE_REGISTERED},
        Status.BLOCKED_TESTER: {Status.CANDIDATE_REGISTERED},
        Status.BLOCKED_ATTRIBUTION: {Status.CANDIDATE_REGISTERED},
    }
    if target not in allowed.get(current, set()):
        raise ValueError("TRANSITION_NOT_AVAILABLE_IN_PHASE5A")
    return target


def readiness(candidate: CandidateInput, binding: Binding) -> Status:
    if candidate.artifact_id is None:
        return Status.DRAFT
    if candidate.license_status != "USER_ATTESTED":
        return Status.BLOCKED_LICENSE
    if not binding.ready():
        return Status.BLOCKED_SYMBOL
    if candidate.tester_access_status != "USER_CONFIRMED":
        return Status.BLOCKED_TESTER
    return Status.BASELINE_READY
