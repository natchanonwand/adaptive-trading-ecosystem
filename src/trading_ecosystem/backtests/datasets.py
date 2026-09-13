"""Read-only verification of the sole authorized frozen dataset run."""

import re
from pathlib import Path

from trading_ecosystem.backtests.contracts import DATA_RUN, EXPECTED_COUNTS, DatasetIdentity
from trading_ecosystem.datasets.contracts import MAPPINGS, Bar, Manifest, Window
from trading_ecosystem.datasets.storage import (
    content_id,
    file_hash,
    object_hash,
    read_json,
    read_parquet,
)
from trading_ecosystem.domain.primitives import Asset, positive_decimal
from trading_ecosystem.research.indicators.observations import validated_bars


def pins(report: str, asset: Asset) -> tuple[str, str, str]:
    section = report.split("### " + asset.value + "\n", 1)[1].split("\n### ", 1)[0]
    values = []
    for label in ("Dataset ID", "Parquet SHA-256", "Manifest SHA-256"):
        match = re.search(re.escape(label) + r": `([0-9a-f]{64})`", section)
        if match is None:
            raise ValueError("MISSING_FROZEN_DATASET_PIN")
        values.append(match.group(1))
    return values[0], values[1], values[2]


def verify_loaded(
    manifest: Manifest,
    bars: tuple[Bar, ...],
    expected: tuple[str, str, str],
    parquet_hash: str,
    manifest_file_hash: str,
) -> None:
    if manifest.dataset_id != expected[0] or parquet_hash != expected[1]:
        raise ValueError("FROZEN_DATASET_IDENTITY_MISMATCH")
    if expected[2] not in (manifest.manifest_hash, manifest_file_hash):
        raise ValueError("FROZEN_MANIFEST_PIN_MISMATCH")
    if manifest.manifest_hash != object_hash(
        manifest.model_dump(mode="json", exclude={"manifest_hash"})
    ):
        raise ValueError("MANIFEST_CONTENT_HASH_MISMATCH")
    if manifest.normalized_parquet_hash != parquet_hash:
        raise ValueError("PARQUET_HASH_MISMATCH")
    validated_bars(bars)
    if manifest.bar_count != len(bars) or len(bars) != EXPECTED_COUNTS[manifest.canonical_asset]:
        raise ValueError("FROZEN_BAR_COUNT_MISMATCH")
    if manifest.broker_symbol != MAPPINGS[manifest.canonical_asset]:
        raise ValueError("SYMBOL_MAPPING_MISMATCH")
    if any(
        bar.dataset_id != manifest.dataset_id
        or bar.canonical_asset != manifest.canonical_asset
        or bar.broker_symbol != manifest.broker_symbol
        or bar.instrument_metadata_reference != manifest.metadata_snapshot_hash
        for bar in bars
    ):
        raise ValueError("BAR_LINEAGE_MISMATCH")
    window = Window(requested_start=manifest.requested_start, requested_end=manifest.requested_end)
    if content_id(bars, window, manifest.canonical_asset.value) != manifest.dataset_id:
        raise ValueError("NORMALIZED_CONTENT_ID_MISMATCH")
    if bars[0].open_time != manifest.actual_start or bars[-1].close_time != manifest.actual_end:
        raise ValueError("COVERAGE_MISMATCH")


def load_asset(root: Path, asset: Asset, report: str) -> tuple[DatasetIdentity, tuple[Bar, ...]]:
    if root.name != DATA_RUN:
        raise ValueError("ONLY_AUTHORIZED_DATASET_RUN_ALLOWED")
    directory = root / asset.value
    manifest = Manifest.model_validate(read_json(directory / "manifest.json"))
    parquet_hash = file_hash(directory / "normalized.parquet")
    manifest_file_hash = file_hash(directory / "manifest.json")
    bars = read_parquet(directory / "normalized.parquet")
    verify_loaded(manifest, bars, pins(report, asset), parquet_hash, manifest_file_hash)
    if manifest.canonical_asset != asset:
        raise ValueError("ASSET_DIRECTORY_MISMATCH")
    metadata_path = directory / "metadata.json"
    if file_hash(metadata_path) != manifest.metadata_snapshot_hash:
        raise ValueError("METADATA_HASH_MISMATCH")
    metadata = read_json(metadata_path)
    if (
        metadata["broker_symbol"] != manifest.broker_symbol
        or metadata["historical_validity"] != "CURRENT_SNAPSHOT_ONLY"
    ):
        raise ValueError("METADATA_SCOPE_MISMATCH")
    ticks = [item["value"] for item in metadata["numeric"] if item["field"] == "trade_tick_size"]
    if len(ticks) != 1:
        raise ValueError("EXPLICIT_VERIFIED_TICK_REQUIRED")
    tick = positive_decimal(ticks[0])
    return DatasetIdentity(
        asset=asset,
        dataset_id=manifest.dataset_id,
        dataset_manifest_hash=manifest.manifest_hash,
        manifest_file_sha256=manifest_file_hash,
        parquet_sha256=parquet_hash,
        metadata_sha256=manifest.metadata_snapshot_hash,
        tick_size=tick,
    ), bars
