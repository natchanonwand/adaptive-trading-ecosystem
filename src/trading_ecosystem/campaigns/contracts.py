"""Campaign identity and user-supplied, local-only licensing/attribution metadata."""

from datetime import timedelta
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from trading_ecosystem.behavioral_research.contracts import ResearchConfig, code_hash
from trading_ecosystem.domain.primitives import FrozenModel, UtcTimestamp
from trading_ecosystem.features.registry import FEATURE_SET_ID
from trading_ecosystem.observer.contracts import Candidate, Config

CHECKPOINT = "4ce8a06"


class EaMetadata(FrozenModel):
    candidate: Candidate
    license_status: Literal["LICENSED_DEMO", "VENDOR_DEMO", "UNATTESTED"] = "UNATTESTED"
    license_attestation_reference: str | None = None
    charts: tuple[str, ...] = ()
    user_confirms_attached: bool = False
    attribution_valid_from: UtcTimestamp | None = None
    settings_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    settings_local_reference: str = Field(min_length=1, max_length=500)
    notes: str = Field(default="", max_length=2000)

    def ready(self) -> bool:
        c = self.candidate
        return bool(
            self.license_status != "UNATTESTED"
            and self.license_attestation_reference
            and self.charts
            and self.user_confirms_attached
            and self.attribution_valid_from is not None
            and c.vendor
            and c.source == "EXTERNAL_EA"
            and c.status == "ACTIVE"
            and c.exclusive_binding
            and c.attribution_reference
            and c.magic_numbers
            and all(m != 0 for m in c.magic_numbers)
            and not any(
                word in (c.ea_id + " " + (c.attribution_reference or "")).upper()
                for word in ("FAKE", "FIXTURE", "SYNTHETIC")
            )
        )


class RealEaQualificationCampaign(FrozenModel):
    schema_version: Literal["REAL_EA_CAMPAIGN_V1"] = "REAL_EA_CAMPAIGN_V1"
    campaign_id: UUID
    metadata: EaMetadata
    account_scope: UUID
    broker: str = Field(min_length=1)
    server: str = Field(min_length=1)
    terminal_build: int = Field(gt=0)
    environment: Literal["DEMO"] = "DEMO"
    dataset_type: Literal["REAL_DEMO_OBSERVATION"] = "REAL_DEMO_OBSERVATION"
    window_start: UtcTimestamp
    window_end: UtcTimestamp
    episode_target: int | None = Field(default=None, ge=1, le=100000)
    bridge_stream_id: UUID
    observer_config: Config
    observer_version: Literal["4B_V1"] = "4B_V1"
    feature_set_id: str = FEATURE_SET_ID
    research_engine_version: str = Field(default_factory=code_hash)
    research_config: ResearchConfig = Field(default_factory=ResearchConfig)
    maximum_gap_seconds: int = Field(default=5, ge=2, le=60)
    api_port: int = Field(default=8765, ge=1024, le=65535)
    dashboard_port: int = Field(default=5173, ge=1024, le=65535)

    @model_validator(mode="after")
    def identity(self) -> Self:
        if not timedelta(0) < self.window_end - self.window_start <= timedelta(days=1):
            raise ValueError("CAMPAIGN_WINDOW_MUST_BE_BOUNDED_TO_ONE_DAY")
        c = self.metadata.candidate
        earliest = self.window_start - timedelta(
            days=self.observer_config.history_days,
            seconds=self.observer_config.overlap_seconds,
        )
        if (
            self.metadata.attribution_valid_from is not None
            and self.metadata.attribution_valid_from > earliest
        ):
            raise ValueError("BINDING_ATTESTATION_MUST_COVER_HISTORY_LOOKBACK")
        if self.observer_config.candidates != (c,) or set(self.observer_config.symbols) != set(
            c.symbols
        ):
            raise ValueError("EXACT_SINGLE_CANDIDATE_BINDING_REQUIRED")
        if not c.symbols or len(set(c.symbols)) != len(c.symbols):
            raise ValueError("DISTINCT_CANDIDATE_SYMBOLS_REQUIRED")
        if self.research_config != ResearchConfig(candidate_id=c.ea_id):
            raise ValueError("FROZEN_DEFAULT_RESEARCH_POLICY_AND_CANDIDATE_FILTER_REQUIRED")
        if self.feature_set_id != FEATURE_SET_ID or self.research_engine_version != code_hash():
            raise ValueError("FROZEN_PIPELINE_VERSION_MISMATCH")
        return self
