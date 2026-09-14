"""Frozen portfolio input contracts and the sole synthetic illustration."""

from datetime import timedelta
from decimal import Decimal
from typing import Literal, Self

from pydantic import model_validator

from trading_ecosystem.benchmarks.contracts import BenchmarkId, ImmutableContract
from trading_ecosystem.domain.primitives import Asset, UtcTimestamp
from trading_ecosystem.simulation.contracts import Digest, Exploratory, Number

ASSET_ORDER = (Asset.BTCUSD, Asset.XAUUSD, Asset.USTEC100)
INPUT_RUN = "phase3_3b-e0a03fae2bf50aadd651586b"
AGGREGATION_VERSION = "realized-episode-r-v0.1.0"


class Interval(ImmutableContract):
    start: UtcTimestamp
    end: UtcTimestamp

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.end <= self.start:
            raise ValueError("EMPTY_COMMON_INTERVAL")
        return self

    def cuts(self) -> tuple[UtcTimestamp, UtcTimestamp]:
        delta = self.end - self.start
        micros = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
        if micros % 5:
            raise ValueError("SPLITS_REQUIRE_EXACT_MICROSECOND_REPRESENTATION")
        return (
            self.start + timedelta(microseconds=micros // 5 * 3),
            self.start + timedelta(microseconds=micros // 5 * 4),
        )

    def split(self, time: UtcTimestamp) -> str:
        first, second = self.cuts()
        return "Development" if time < first else "Validation" if time < second else "Locked OOS"


class Episode(Exploratory):
    episode_id: Digest
    asset: Asset
    benchmark_id: BenchmarkId
    signal_time: UtcTimestamp
    entry_time: UtcTimestamp
    exit_time: UtcTimestamp | None
    gross_price_R: Number | None
    entry_priority: int = 30
    entry_sequence: int
    exit_priority: int | None
    exit_sequence: int | None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.entry_time <= self.signal_time:
            raise ValueError("ENTRY_MUST_FOLLOW_DECISION")
        if self.exit_time is not None:
            if self.exit_time < self.entry_time or self.gross_price_R is None:
                raise ValueError("INVALID_COMPLETED_EPISODE")
            if self.exit_priority is None or self.exit_sequence is None:
                raise ValueError("MISSING_EXIT_ORDERING")
        elif self.gross_price_R is not None:
            raise ValueError("OPEN_EPISODE_HAS_REALIZED_OUTCOME")
        return self


class Scenario(ImmutableContract):
    scenario_id: Literal["SYNTHETIC_300USD_RISK025_V0"] = "SYNTHETIC_300USD_RISK025_V0"
    model_version: Literal["constant-fraction-realized-v0.1.0"] = (
        "constant-fraction-realized-v0.1.0"
    )
    initial_equity_usd: Literal["300"] = "300"
    risk_fraction: Literal["0.0025"] = "0.0025"
    aggregate_risk_cap: Literal["0.0075"] = "0.0075"
    cash_tolerance: Literal["0.0000000000000000000000000001"] = "0.0000000000000000000000000001"
    max_concurrent: Literal[3] = 3
    max_per_asset: Literal[1] = 1
    direction: Literal["LONG_ONLY"] = "LONG_ONLY"


SCENARIO = Scenario()
ZERO = Decimal(0)
