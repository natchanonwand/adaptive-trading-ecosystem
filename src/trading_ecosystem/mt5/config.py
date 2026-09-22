"""Explicit aliases and bounded cadences; configuration never contains credentials."""

from pydantic import Field, model_validator

from trading_ecosystem.domain.primitives import FrozenModel


class BridgeConfig(FrozenModel):
    aliases: dict[str, str]
    account_seconds: int = Field(default=1, ge=1, le=60)
    positions_seconds: int = Field(default=1, ge=1, le=60)
    quotes_seconds: int = Field(default=1, ge=1, le=60)
    health_seconds: int = Field(default=5, ge=1, le=30)
    history_seconds: int = Field(default=10, ge=5, le=300)
    metadata_seconds: int = Field(default=300, ge=30, le=86400)
    stale_seconds: int = Field(default=30, ge=5, le=300)
    overlap_seconds: int = Field(default=120, ge=1, le=3600)
    initial_history_days: int = Field(default=7, ge=1, le=30)
    history_window_seconds: int = Field(default=3600, ge=60, le=86400)
    max_history_records: int = Field(default=10000, ge=1, le=100000)
    retry_seconds: int = Field(default=2, ge=1, le=30)
    retry_cap_seconds: int = Field(default=30, ge=1, le=300)

    @model_validator(mode="after")
    def aliases_valid(self) -> "BridgeConfig":
        if self.history_window_seconds <= self.overlap_seconds:
            raise ValueError("HISTORY_WINDOW_MUST_EXCEED_OVERLAP")
        if not self.aliases or len(set(self.aliases.values())) != len(self.aliases):
            raise ValueError("EXPLICIT_UNAMBIGUOUS_ALIASES_REQUIRED")
        if any(not k or not v or len(k) > 64 or len(v) > 128 for k, v in self.aliases.items()):
            raise ValueError("INVALID_ALIAS")
        return self
