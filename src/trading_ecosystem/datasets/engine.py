"""Bounded, auditable ingestion using only the Phase 2A DEMO-gated provider."""

from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import ValidationError

from trading_ecosystem.datasets.contracts import (
    HOUR,
    MAPPINGS,
    Bar,
    Chunk,
    Manifest,
    QuarantinedObservation,
    Window,
    strict_utc,
)
from trading_ecosystem.datasets.storage import (
    code_hash,
    content_id,
    file_hash,
    object_hash,
    write_json,
    write_parquet,
)
from trading_ecosystem.datasets.validation import assess
from trading_ecosystem.discovery.contracts import DemoRequired, DiscoveryError, H1Batch
from trading_ecosystem.discovery.provider import Mt5ReadOnlyProvider
from trading_ecosystem.domain.primitives import Asset


def chunks(window: Window) -> tuple[Window, ...]:
    result = []
    start = window.requested_start
    while start < window.requested_end:
        end = min(start + timedelta(days=31), window.requested_end)
        result.append(Window(requested_start=start, requested_end=end))
        start = end
    return tuple(result)


def normalize(
    batch: H1Batch,
    asset: Asset,
    metadata_hash: str,
    retrieved: datetime,
    source_version: str | None,
    window: Window,
    source_file: str,
) -> tuple[list[Bar], int, int, tuple[str, ...], tuple[QuarantinedObservation, ...]]:
    bars = []
    invalid = invalid_ohlc = 0
    issues = []
    quarantine = []
    for row_index, row in enumerate(batch.rows):
        # Unknown/invalid times cannot safely be classified as outside coverage.
        try:
            time = strict_utc(row.time)
            if time.minute or time.second or time.microsecond:
                raise ValueError("H1_ALIGNMENT")
        except ValueError:
            invalid += 1
            issues.append("INVALID_SOURCE_TIMESTAMP")
            continue
        if not window.requested_start <= time < window.requested_end:
            quarantine.append(
                QuarantinedObservation(
                    **window.model_dump(),
                    source_file=source_file,
                    row_index=row_index,
                    observed_time=time,
                )
            )
            continue
        values = row.model_dump(exclude={"time"})
        prices = (row.open, row.high, row.low, row.close)
        if all(value is not None for value in prices):
            o, h, low, c = prices
            assert o is not None and h is not None and low is not None and c is not None
            if min(o, h, low, c) <= 0 or not low <= min(o, c) <= max(o, c) <= h:
                invalid_ohlc += 1
        try:
            bar = Bar.model_validate(
                {
                    **values,
                    "dataset_id": "pending",
                    "canonical_asset": asset,
                    "broker_symbol": MAPPINGS[asset],
                    "instrument_metadata_reference": metadata_hash,
                    "open_time": row.time,
                    "close_time": row.time + HOUR if row.time else None,
                    "available_at": row.time + HOUR if row.time else None,
                    "retrieved_at": retrieved,
                    "source_version": source_version,
                }
            )
            bars.append(bar)
        except ValidationError:
            invalid += 1
            issues.append("INVALID_SOURCE_RECORD")
    return bars, invalid, invalid_ohlc, tuple(issues), tuple(quarantine)


def ingest(
    provider: Mt5ReadOnlyProvider, asset: Asset, window: Window, directory: Path
) -> Manifest:
    identity = provider.get_provider_identity()
    if identity.company != "Exness Technologies Ltd" or identity.server != "Exness-MT5Trial14":
        raise DiscoveryError("BROKER_REFERENCE_MISMATCH")
    metadata = provider.get_instrument_metadata(MAPPINGS[asset])
    if metadata.broker_symbol != MAPPINGS[asset]:
        raise DiscoveryError("METADATA_SYMBOL_MISMATCH")
    # An existing directory is never reused, including an interrupted run.
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "metadata.json", metadata.model_dump(mode="json"))
    write_json(directory / "provider.json", identity.model_dump(mode="json"))
    metadata_hash = file_hash(directory / "metadata.json")
    try:
        source_version = version("MetaTrader5")
    except PackageNotFoundError:
        source_version = None
    records = []
    bars = []
    invalid = invalid_ohlc = failed = 0
    issues: list[str] = []
    quarantine: list[QuarantinedObservation] = []
    for index, interval in enumerate(chunks(window)):
        error: str | None = None
        try:
            batch = provider.get_h1_bars(
                MAPPINGS[asset], interval.requested_start, interval.requested_end
            )
            error = batch.error
        except DemoRequired:
            # Preserve an error receipt, then stop without another terminal query.
            batch = H1Batch(rows=())
            error = "DEMO_GATE_ABORTED"
        except DiscoveryError:
            batch = H1Batch(rows=())
            error = "PROVIDER_READ_FAILED"
        retrieved = datetime.now(UTC)
        source_name = f"chunk-{index:04d}.json"
        times = [row.time for row in batch.rows if row.time is not None]
        raw = {
            "canonical_asset": asset.value,
            "broker_symbol": MAPPINGS[asset],
            **interval.model_dump(mode="json"),
            "retrieved_at": retrieved.isoformat(),
            "source_version": source_version,
            "provider_error": error,
            "rows": batch.model_dump(mode="json")["rows"],
        }
        write_json(directory / source_name, raw)
        record = Chunk(
            **interval.model_dump(),
            canonical_asset=asset,
            broker_symbol=MAPPINGS[asset],
            retrieved_at=retrieved,
            row_count=len(batch.rows),
            first_bar=min(times) if times else None,
            last_bar=max(times) if times else None,
            status="ERROR" if error else "OBSERVED" if batch.rows else "EMPTY",
            error=error,
            source_file=source_name,
            source_hash=file_hash(directory / source_name),
        )
        records.append(record)
        write_json(directory / f"receipt-{index:04d}.json", record.model_dump(mode="json"))
        converted, count, ohlc, chunk_issues, excluded = normalize(
            batch, asset, metadata_hash, retrieved, source_version, interval, source_name
        )
        quarantine.extend(excluded)
        bars.extend(converted)
        invalid += count
        invalid_ohlc += ohlc
        failed += int(error is not None)
        issues.extend(chunk_issues)
        if error == "DEMO_GATE_ABORTED":
            write_json(directory / "abort.json", record.model_dump(mode="json"))
            quality = assess(
                bars,
                window,
                invalid=invalid,
                invalid_ohlc=invalid_ohlc,
                failed=failed,
                issues=tuple(issues),
                quarantine=tuple(quarantine),
            )
            write_json(directory / "quality.json", quality.model_dump(mode="json"))
            raise DemoRequired("DEMO_GATE_ABORTED")
    quality = assess(
        bars,
        window,
        invalid=invalid,
        invalid_ohlc=invalid_ohlc,
        failed=failed,
        issues=tuple(issues),
        quarantine=tuple(quarantine),
    )
    write_json(directory / "quality.json", quality.model_dump(mode="json"))
    if quality.validation_status != "PASS":
        raise DiscoveryError("DATASET_VALIDATION_FAILED_EVIDENCE_PRESERVED")
    dataset_id = content_id(bars, window, asset.value)
    bars = [bar.model_copy(update={"dataset_id": dataset_id}) for bar in bars]
    write_parquet(directory / "normalized.parquet", bars)
    fields = dict(
        dataset_id=dataset_id,
        canonical_asset=asset,
        broker_symbol=MAPPINGS[asset],
        **window.model_dump(),
        actual_start=bars[0].open_time if bars else None,
        actual_end=bars[-1].close_time if bars else None,
        provider_snapshot_hash=file_hash(directory / "provider.json"),
        metadata_snapshot_hash=metadata_hash,
        normalized_parquet_hash=file_hash(directory / "normalized.parquet"),
        quality_hash=file_hash(directory / "quality.json"),
        chunks=tuple(records),
        code_hash=code_hash(),
        bar_count=len(bars),
        gap_count=len(quality.gaps),
        manifest_hash="0" * 64,
    )
    manifest = Manifest.model_validate(fields)
    manifest = manifest.model_copy(
        update={
            "manifest_hash": object_hash(
                manifest.model_dump(mode="json", exclude={"manifest_hash"})
            )
        }
    )
    # Manifest is the completion marker, written only after all evidence exists.
    write_json(directory / "manifest.json", manifest.model_dump(mode="json"))
    return manifest
