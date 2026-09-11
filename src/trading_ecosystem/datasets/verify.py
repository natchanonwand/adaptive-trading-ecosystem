"""Verify persisted evidence, normalized identity, schema, lineage and quality."""

import argparse
from pathlib import Path

from trading_ecosystem.datasets.contracts import (
    MAPPINGS,
    Bar,
    Manifest,
    Quality,
    QuarantinedObservation,
    Window,
    strict_utc,
)
from trading_ecosystem.datasets.engine import chunks, normalize
from trading_ecosystem.datasets.storage import (
    content_id,
    file_hash,
    object_hash,
    read_json,
    read_parquet,
)
from trading_ecosystem.datasets.validation import assess
from trading_ecosystem.discovery.contracts import H1Batch, InstrumentMetadata, ProviderIdentity


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def verify(directory: Path) -> Manifest:
    manifest = Manifest.model_validate(read_json(directory / "manifest.json"))
    require(manifest.broker_symbol == MAPPINGS[manifest.canonical_asset], "MAPPING_MISMATCH")
    require(
        manifest.manifest_hash
        == object_hash(manifest.model_dump(mode="json", exclude={"manifest_hash"})),
        "MANIFEST_HASH_MISMATCH",
    )
    for name, expected in (
        ("normalized.parquet", manifest.normalized_parquet_hash),
        ("metadata.json", manifest.metadata_snapshot_hash),
        ("provider.json", manifest.provider_snapshot_hash),
        ("quality.json", manifest.quality_hash),
    ):
        require(file_hash(directory / name) == expected, "FILE_HASH_MISMATCH")
    metadata = InstrumentMetadata.model_validate(read_json(directory / "metadata.json"))
    require(metadata.broker_symbol == manifest.broker_symbol, "METADATA_MISMATCH")
    provider = ProviderIdentity.model_validate(read_json(directory / "provider.json"))
    require(
        provider.company == manifest.broker_company and provider.server == manifest.server,
        "PROVIDER_MISMATCH",
    )
    bars = read_parquet(directory / "normalized.parquet")
    window = Window(requested_start=manifest.requested_start, requested_end=manifest.requested_end)
    require(
        manifest.dataset_id == content_id(bars, window, manifest.canonical_asset.value),
        "CONTENT_ID_MISMATCH",
    )
    require(
        all(
            bar.dataset_id == manifest.dataset_id
            and bar.canonical_asset == manifest.canonical_asset
            and bar.instrument_metadata_reference == manifest.metadata_snapshot_hash
            for bar in bars
        ),
        "BAR_LINEAGE_MISMATCH",
    )
    intervals = chunks(window)
    require(len(intervals) == len(manifest.chunks), "CHUNK_COUNT_MISMATCH")
    rebuilt: list[Bar] = []
    quarantine: list[QuarantinedObservation] = []
    for index, (interval, receipt) in enumerate(zip(intervals, manifest.chunks, strict=True)):
        require(
            receipt.requested_start == interval.requested_start
            and receipt.requested_end == interval.requested_end
            and receipt.canonical_asset == manifest.canonical_asset
            and receipt.broker_symbol == manifest.broker_symbol
            and receipt.error is None,
            "CHUNK_CONTRACT_MISMATCH",
        )
        require(receipt.source_file == f"chunk-{index:04d}.json", "CHUNK_PATH_MISMATCH")
        require(
            read_json(directory / f"receipt-{index:04d}.json") == receipt.model_dump(mode="json"),
            "RECEIPT_MISMATCH",
        )
        raw_path = directory / receipt.source_file
        require(file_hash(raw_path) == receipt.source_hash, "SOURCE_HASH_MISMATCH")
        raw = read_json(raw_path)
        require(
            raw["canonical_asset"] == manifest.canonical_asset
            and raw["broker_symbol"] == manifest.broker_symbol
            and Window.model_validate({key: raw[key] for key in Window.model_fields}) == interval
            and strict_utc(raw["retrieved_at"]) == receipt.retrieved_at
            and raw["provider_error"] is None,
            "RAW_CONTRACT_MISMATCH",
        )
        batch = H1Batch.model_validate({"rows": raw["rows"]})
        converted, invalid, ohlc, issues, excluded = normalize(
            batch,
            manifest.canonical_asset,
            manifest.metadata_snapshot_hash,
            receipt.retrieved_at,
            raw["source_version"],
            interval,
            receipt.source_file,
        )
        quarantine.extend(excluded)
        require(not (invalid or ohlc or issues), "RAW_VALIDATION_FAILED")
        times = [row.time for row in batch.rows if row.time is not None]
        require(
            len(batch.rows) == receipt.row_count
            and receipt.first_bar == (min(times) if times else None)
            and receipt.last_bar == (max(times) if times else None)
            and receipt.status == ("OBSERVED" if times else "EMPTY"),
            "RECEIPT_STATISTICS_MISMATCH",
        )
        rebuilt.extend(
            bar.model_copy(update={"dataset_id": manifest.dataset_id}) for bar in converted
        )
    require(tuple(rebuilt) == bars, "RAW_PARQUET_MISMATCH")
    quality = Quality.model_validate(read_json(directory / "quality.json"))
    require(
        assess(bars, window, quarantine=tuple(quarantine)) == quality
        and quality.validation_status == "PASS",
        "QUALITY_MISMATCH",
    )
    require(
        manifest.bar_count == len(bars)
        and manifest.gap_count == len(quality.gaps)
        and manifest.actual_start == (bars[0].open_time if bars else None)
        and manifest.actual_end == (bars[-1].close_time if bars else None),
        "COVERAGE_MISMATCH",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--require-all-assets", action="store_true")
    args = parser.parse_args()
    manifests = sorted(args.root.rglob("manifest.json"))
    if not manifests:
        parser.error("No completed manifests found")
    if args.require_all_assets:
        runs = {path.parent.parent for path in manifests}
        for run in runs:
            assets = {path.parent.name for path in manifests if path.parent.parent == run}
            require(assets == set(MAPPINGS), "ALL_THREE_ASSET_DATASETS_REQUIRED")
    for path in manifests:
        result = verify(path.parent)
        print(f"PASS {result.canonical_asset}: {result.bar_count} bars; {result.dataset_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
