"""Versioned research policy. Sample tiers are explicit operational counts, not truth scores."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from trading_ecosystem.domain.primitives import FrozenModel

Record = dict[str, Any]
SCHEMA = "BEHAVIORAL_RESEARCH_V1"
FINGERPRINT_SCHEMA = "BEHAVIOR_FINGERPRINT_V1"
CHECKPOINT = "90e9091"
DatasetType = Literal["SYNTHETIC_QUALIFICATION", "REAL_DEMO_OBSERVATION"]


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def identity(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def code_hash() -> str:
    return hashlib.sha256(
        b"".join(
            p.name.encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n")
            for p in sorted(Path(__file__).parent.glob("*.py"))
        )
    ).hexdigest()


class ResearchConfig(FrozenModel):
    schema_version: Literal["BEHAVIORAL_RESEARCH_V1"] = "BEHAVIORAL_RESEARCH_V1"
    seed: int = Field(default=1729, ge=0, le=2**32 - 1)
    bootstrap_replicates: int = Field(default=200, ge=100, le=2000)
    preliminary_n: int = Field(default=30, ge=3)
    usable_n: int = Field(default=100, ge=3)
    stronger_n: int = Field(default=300, ge=3)
    minimum_sessions: int = Field(default=3, ge=2)
    hypothesis_coverage: Decimal = Field(default=Decimal(".8"), gt=0, le=1)
    agreement_threshold: Decimal = Field(default=Decimal(".7"), gt=Decimal(".5"), lt=1)
    quantile_probabilities: tuple[Decimal, ...] = (Decimal(".25"), Decimal(".5"), Decimal(".75"))
    rsi_edges: tuple[Decimal, ...] = (Decimal(30), Decimal(70))
    candidate_id: str | None = None
    session_id: str | None = None
    symbol: str | None = None

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not self.preliminary_n < self.usable_n < self.stronger_n:
            raise ValueError("EVIDENCE_TIERS_MUST_INCREASE")
        for values in (self.quantile_probabilities, self.rsi_edges):
            if not values or any(not v.is_finite() for v in values):
                raise ValueError("FINITE_NONEMPTY_BIN_DEFINITIONS_REQUIRED")
            if tuple(sorted(set(values))) != values:
                raise ValueError("BIN_DEFINITIONS_MUST_INCREASE")
        if any(not 0 < v < 1 for v in self.quantile_probabilities):
            raise ValueError("INVALID_QUANTILE_PROBABILITY")
        if any(not 0 < v < 100 for v in self.rsi_edges):
            raise ValueError("INVALID_RSI_EDGE")
        if any(
            v is not None and not v.strip()
            for v in (self.candidate_id, self.session_id, self.symbol)
        ):
            raise ValueError("EMPTY_RESEARCH_FILTER")
        return self


BehaviorFamily = Literal[
    "TREND_ALIGNMENT",
    "MEAN_REVERSION_LIKE_ENTRY",
    "BREAKOUT_LIKE_ENTRY",
    "VOLATILITY_FILTERING",
    "SESSION_FILTERING",
    "FIXED_SL_TP",
    "ATR_SCALED_EXITS",
    "SCALE_IN",
    "GRID_LIKE_SPACING",
    "VOLUME_PROGRESSION",
    "BASKET_CLOSE",
]


class BehaviorHypothesis(FrozenModel):
    hypothesis_id: str
    hypothesis_type: BehaviorFamily
    description: str
    supporting_metrics: tuple[str, ...]
    contradicting_metrics: tuple[str, ...]
    sample_size: int
    known_count: int
    missing_count: int
    coverage: str
    confidence: Literal["SAMPLE_SUFFICIENCY_ONLY"] = "SAMPLE_SUFFICIENCY_ONLY"
    dataset_type: Literal["REAL_DEMO_OBSERVATION"] = "REAL_DEMO_OBSERVATION"
    status: Literal[
        "INSUFFICIENT_DATA",
        "WEAK_EVIDENCE",
        "SUPPORTED_BY_CURRENT_SAMPLE",
        "CONTRADICTED_BY_CURRENT_SAMPLE",
    ]


class BehaviorFingerprint(FrozenModel):
    fingerprint_schema_version: Literal["BEHAVIOR_FINGERPRINT_V1"] = "BEHAVIOR_FINGERPRINT_V1"
    fingerprint_version: str
    definition_hash: str
    research_config_hash: str
    feature_set_id: str
    dataset_hash: str
    n: int
    known_count: int
    missing_count: int
    measurements: Record
