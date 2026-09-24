"""Explicit configuration and immutable feature definitions."""

from typing import Literal, Self

from pydantic import Field, model_validator

from trading_ecosystem.domain.primitives import FrozenModel

SCHEMA_VERSION = "BEHAVIORAL_FEATURES_V1"
BUILDER_VERSION = "4C_V1_DECIMAL34"


class SessionWindow(FrozenModel):
    name: str
    start_minute_utc: int = Field(ge=0, lt=1440)
    end_minute_utc: int = Field(ge=0, lt=1440)

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if self.start_minute_utc == self.end_minute_utc:
            raise ValueError("EMPTY_SESSION_WINDOW")
        return self


class BuildConfig(FrozenModel):
    schema_version: Literal["BEHAVIORAL_FEATURES_V1"] = "BEHAVIORAL_FEATURES_V1"
    builder_version: Literal["4C_V1_DECIMAL34"] = "4C_V1_DECIMAL34"
    dataset_type: Literal["SYNTHETIC_QUALIFICATION", "REAL_DEMO_OBSERVATION"] = (
        "SYNTHETIC_QUALIFICATION"
    )
    provenance_reference: str = "PHASE4B_DETERMINISTIC_QUALIFICATION"
    session_windows: tuple[SessionWindow, ...] = (
        SessionWindow(name="UTC_00_08", start_minute_utc=0, end_minute_utc=480),
        SessionWindow(name="UTC_08_16", start_minute_utc=480, end_minute_utc=960),
        SessionWindow(name="UTC_16_00", start_minute_utc=960, end_minute_utc=0),
    )
    recent_quote_count: int = Field(default=20, ge=2, le=100)

    @model_validator(mode="after")
    def names(self) -> Self:
        if len({w.name for w in self.session_windows}) != len(self.session_windows):
            raise ValueError("DUPLICATE_SESSION_NAME")
        if not self.provenance_reference.strip():
            raise ValueError("PROVENANCE_REQUIRED")
        return self


class Definition(FrozenModel):
    name: str
    version: Literal[1] = 1
    family: str
    dtype: Literal["decimal", "integer", "boolean", "string", "decimal_sequence"]
    definition: str
    source: str
    lookback: int | None = None
    timeframe: str | None = None
    availability: str
    nullable: bool = True
    causal: bool
