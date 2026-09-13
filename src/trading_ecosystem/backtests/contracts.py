"""Frozen single-asset research provenance and split contracts."""

from enum import StrEnum
from typing import Literal

from trading_ecosystem.benchmarks.contracts import ImmutableContract
from trading_ecosystem.domain.primitives import Asset, Price, UtcTimestamp
from trading_ecosystem.simulation.contracts import Digest, Exploratory

DATA_RUN = "20260911T161046Z-ee75c598"
EXPECTED_COUNTS = {Asset.BTCUSD: 36036, Asset.XAUUSD: 33647, Asset.USTEC100: 23977}


class DatasetIdentity(Exploratory):
    asset: Asset
    dataset_id: str
    dataset_manifest_hash: Digest
    manifest_file_sha256: Digest
    parquet_sha256: Digest
    metadata_sha256: Digest
    tick_size: Price
    dataset_run: Literal["20260911T161046Z-ee75c598"] = "20260911T161046Z-ee75c598"
    instrument_metadata_temporal_scope: Literal["CURRENT_SNAPSHOT_ONLY"] = "CURRENT_SNAPSHOT_ONLY"


class SplitName(StrEnum):
    DEVELOPMENT = "Development"
    VALIDATION = "Validation"
    LOCKED_OOS = "Locked OOS"


class Split(ImmutableContract):
    name: SplitName
    first_index: int
    end_index_exclusive: int
    first_decision_time: UtcTimestamp
    last_decision_time: UtcTimestamp


class MetricState(StrEnum):
    FINITE = "FINITE"
    UNDEFINED = "UNDEFINED"
    POSITIVE_INFINITY = "POSITIVE_INFINITY"
