import json
import subprocess
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.discovery.test_discovery import FakeSdk
from trading_ecosystem.datasets.contracts import HOUR, MAPPINGS, Bar, Window
from trading_ecosystem.datasets.engine import chunks, ingest
from trading_ecosystem.datasets.storage import (
    content_id,
    object_hash,
    read_parquet,
    write_parquet,
)
from trading_ecosystem.datasets.validation import assess
from trading_ecosystem.datasets.verify import verify
from trading_ecosystem.discovery.contracts import DemoRequired, DiscoveryError
from trading_ecosystem.discovery.provider import Mt5ReadOnlyProvider
from trading_ecosystem.domain.primitives import Asset

NOW = datetime(2026, 1, 1, tzinfo=UTC)
WINDOW = Window(requested_start=NOW, requested_end=NOW + 4 * HOUR)


def bar(**changes: object) -> Bar:
    values: dict[str, object] = dict(
        dataset_id="synthetic",
        canonical_asset=Asset.BTCUSD,
        broker_symbol="BTCUSDm",
        instrument_metadata_reference="0" * 64,
        open_time=NOW,
        close_time=NOW + HOUR,
        available_at=NOW + HOUR,
        open="10",
        high="12",
        low="9",
        close="11",
        tick_volume=10,
        spread_points=1,
        real_volume=0,
        retrieved_at=NOW,
    )
    return Bar.model_validate({**values, **changes})


class DatasetSdk(FakeSdk):
    def account_info(self) -> dict[str, object]:
        return {
            "trade_mode": self.mode,
            "company": "Exness Technologies Ltd",
            "server": "Exness-MT5Trial14",
            "currency": "USD",
        }


def sdk_row(**changes: object) -> dict[str, object]:
    return {
        "time": int(NOW.timestamp()),
        "open": 10,
        "high": 12,
        "low": 9,
        "close": 11,
        "tick_volume": 10,
        "spread": 1,
        "real_volume": 0,
        **changes,
    }


def dataset(tmp_path: Path) -> Path:
    sdk = DatasetSdk()
    sdk.bars = [sdk_row(), sdk_row(time=int((NOW + 2 * HOUR).timestamp()))]
    path = tmp_path / "dataset"
    with Mt5ReadOnlyProvider(sdk) as provider:
        ingest(provider, Asset.BTCUSD, WINDOW, path)
    return path


@pytest.mark.parametrize("asset,symbol", list(MAPPINGS.items()))
def test_approved_mappings(asset: str, symbol: str) -> None:
    assert bar(canonical_asset=asset, broker_symbol=symbol).broker_symbol == symbol


@pytest.mark.parametrize("symbol", ["BTCUSD", "XAUUSD", "USTEC100", "NAS100", "USTEC", "BTCUSDx"])
def test_alternatives_rejected(symbol: str) -> None:
    with pytest.raises(ValidationError):
        bar(broker_symbol=symbol)
    with Mt5ReadOnlyProvider(DatasetSdk()) as provider, pytest.raises(DiscoveryError):
        provider.get_h1_bars(symbol, NOW, NOW + HOUR)


@pytest.mark.parametrize("field", ["open_time", "close_time", "available_at", "retrieved_at"])
@pytest.mark.parametrize(
    "value", [datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=7)))]
)
def test_timestamp_enforcement(field: str, value: datetime) -> None:
    with pytest.raises(ValidationError):
        bar(**{field: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"open_time": NOW + timedelta(minutes=1)},
        {"close_time": NOW + 2 * HOUR},
        {"available_at": NOW},
        {"high": "8"},
        {"high": "10"},
        {"low": "11"},
        {"open": "13"},
        {"close": "8"},
        {"open": "0"},
        {"close": "-1"},
        {"high": "NaN"},
        {"low": "Infinity"},
        {"open": "malformed"},
        {"open": 10.0},
        {"open": True},
        {"open": "0.0000000000000000001"},
        {"high": "1e20"},
        {"tick_volume": -1},
        {"spread_points": 0.5},
        {"real_volume": True},
        {"tick_volume": 2**63},
        {"quality_flags": ["QUALIFIED"]},
        {"timeframe": "M1"},
        {"price_basis": "BID"},
    ],
)
def test_invalid_contracts(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        bar(**changes)


def test_immutable_contract_and_mappings() -> None:
    with pytest.raises(ValidationError):
        bar().open = Decimal("3")  # type: ignore[misc]
    with pytest.raises(TypeError):
        MAPPINGS["BTCUSD"] = "alternative"  # type: ignore[index]


@pytest.mark.parametrize("delta", [HOUR, timedelta(days=31), timedelta(days=62, hours=3)])
def test_deterministic_chunks(delta: timedelta) -> None:
    window = Window(requested_start=NOW, requested_end=NOW + delta)
    result = chunks(window)
    assert result == chunks(window)
    assert result[0].requested_start == NOW and result[-1].requested_end == NOW + delta
    assert all(
        chunk.requested_end - chunk.requested_start <= timedelta(days=31) for chunk in result
    )
    assert all(
        a.requested_end == b.requested_start for a, b in zip(result, result[1:], strict=False)
    )


@pytest.mark.parametrize("end", [NOW, NOW - HOUR, NOW + timedelta(minutes=5)])
def test_bad_window(end: datetime) -> None:
    with pytest.raises(ValidationError):
        Window(requested_start=NOW, requested_end=end)


def test_duplicates_conflicts_order_and_boundaries() -> None:
    result = assess([bar(), bar(), bar(close="10")], WINDOW)
    assert result.validation_status == "FAIL"
    assert result.duplicate_count == 2 and result.conflicting_duplicate_count == 1
    late = bar(open_time=NOW + 5 * HOUR, close_time=NOW + 6 * HOUR, available_at=NOW + 6 * HOUR)
    result = assess([late, bar()], WINDOW)
    assert {"OUTSIDE_REQUESTED_BOUNDARIES", "UNEXPECTED_ORDERING"} <= set(result.issues)


def test_gaps_include_edges_and_never_fill() -> None:
    sample = bar(open_time=NOW + HOUR, close_time=NOW + 2 * HOUR, available_at=NOW + 2 * HOUR)
    result = assess([sample], WINDOW)
    assert result.bar_count == 1 and result.missing_clock_hours == 3
    assert result.largest_gap == 2 and len(result.gaps) == 2
    assert all(gap.classification == "UNCLASSIFIED_GAP" for gap in result.gaps)
    assert result.gaps[0].previous_bar is None and result.gaps[-1].next_bar is None
    empty = assess([], WINDOW)
    assert empty.missing_clock_hours == 4 and empty.bar_count == 0


@pytest.mark.parametrize("price", ["10", "10.123456789012345678", "0.000000000000000001"])
def test_exact_parquet(tmp_path: Path, price: str) -> None:
    sample = bar(open=price, high=price, low=price, close=price)
    path = tmp_path / "bars.parquet"
    write_parquet(path, [sample])
    assert read_parquet(path) == (sample,)
    assert read_parquet(path)[0].open == Decimal(price)
    with pytest.raises(FileExistsError):
        write_parquet(path, [])


def test_content_identity_excludes_operational_provenance() -> None:
    expected = content_id([bar()], WINDOW, "BTCUSD")
    assert content_id([bar(retrieved_at=NOW + HOUR)], WINDOW, "BTCUSD") == expected
    assert content_id([bar(instrument_metadata_reference="1" * 64)], WINDOW, "BTCUSD") == expected
    assert content_id([bar(close="10")], WINDOW, "BTCUSD") != expected
    assert content_id([bar(open="10.00")], WINDOW, "BTCUSD") == expected


def test_complete_ingestion_and_independent_verification(tmp_path: Path) -> None:
    path = dataset(tmp_path)
    manifest = verify(path)
    assert manifest.bar_count == 2 and manifest.qualification_eligible is False
    assert manifest.actual_end == NOW + 3 * HOUR and manifest.requested_end == NOW + 4 * HOUR
    values = manifest.model_dump(mode="json", exclude={"manifest_hash"})
    assert object_hash({**values, "metadata_snapshot_hash": "1" * 64}) != manifest.manifest_hash
    sdk = DatasetSdk()
    with Mt5ReadOnlyProvider(sdk) as provider, pytest.raises(FileExistsError):
        ingest(provider, Asset.BTCUSD, WINDOW, path)
    for file in path.glob("*.json"):
        text = file.read_text()
        assert not any(f'"{key}"' in text for key in ("login", "password", "account_id"))


@pytest.mark.parametrize(
    "name",
    [
        "normalized.parquet",
        "metadata.json",
        "quality.json",
        "chunk-0000.json",
        "receipt-0000.json",
        "manifest.json",
    ],
)
def test_tampering_detected(tmp_path: Path, name: str) -> None:
    path = dataset(tmp_path)
    target = path / name
    target.write_bytes(target.read_bytes() + b" ")
    if name in {"receipt-0000.json", "manifest.json"}:
        values = json.loads(target.read_bytes())
        values["bar_count" if name == "manifest.json" else "row_count"] = 999
        target.write_text(json.dumps(values))
    with pytest.raises((ValueError, OSError)):
        verify(path)


@pytest.mark.parametrize(
    "rows",
    [
        None,
        [sdk_row(time=0)],
        [sdk_row(high=8)],
        [sdk_row(), sdk_row()],
        [sdk_row(), sdk_row(close=10)],
    ],
)
def test_bad_chunks_preserved_and_cannot_publish(tmp_path: Path, rows: object) -> None:
    sdk = DatasetSdk()
    sdk.bars = rows  # type: ignore[assignment]
    path = tmp_path / "failed"
    with Mt5ReadOnlyProvider(sdk) as provider, pytest.raises(DiscoveryError):
        ingest(provider, Asset.BTCUSD, WINDOW, path)
    assert (path / "chunk-0000.json").exists() and (path / "quality.json").exists()
    assert not (path / "manifest.json").exists()
    assert json.loads((path / "quality.json").read_bytes())["validation_status"] == "FAIL"


@pytest.mark.parametrize("mode", [1, 2, None, "0", True, 99])
def test_demo_gate_unchanged(mode: object) -> None:
    with pytest.raises(DemoRequired), Mt5ReadOnlyProvider(DatasetSdk(mode)):
        pytest.fail("must not enter")


def test_raw_path_preserves_malformed_and_outside_rows() -> None:
    sdk = DatasetSdk()
    sdk.bars = [sdk_row(time=0), sdk_row(time=int((NOW - HOUR).timestamp()))]
    with Mt5ReadOnlyProvider(sdk) as provider:
        batch = provider.get_h1_bars("BTCUSDm", NOW, NOW + HOUR)
    assert len(batch.rows) == 2 and batch.rows[0].time is None
    assert batch.rows[1].time == NOW - HOUR
    assert "copy_ticks_range" not in sdk.calls


def test_generated_evidence_ignored() -> None:
    names = [
        f"data/datasets/synthetic/{name}"
        for name in (
            "normalized.parquet",
            "metadata.json",
            "manifest.json",
            "quality.json",
            "chunk-0000.json",
        )
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", *names], capture_output=True, text=True, check=False
    )
    assert set(result.stdout.splitlines()) == set(names)


def test_every_failed_chunk_has_receipt(tmp_path: Path) -> None:
    sdk = DatasetSdk()
    sdk.bars = None
    window = Window(requested_start=NOW, requested_end=NOW + timedelta(days=63))
    target = tmp_path / "failed"
    with Mt5ReadOnlyProvider(sdk) as provider, pytest.raises(DiscoveryError):
        ingest(provider, Asset.BTCUSD, window, target)
    assert len(list(target.glob("receipt-*.json"))) == 3
    assert len(list(target.glob("chunk-*.json"))) == 3
    quality = json.loads((target / "quality.json").read_bytes())
    assert quality["failed_chunk_count"] == 3
    assert quality["bar_count"] == 0


def test_empty_successful_coverage_is_honest(tmp_path: Path) -> None:
    with Mt5ReadOnlyProvider(DatasetSdk()) as provider:
        manifest = ingest(provider, Asset.XAUUSD, WINDOW, tmp_path / "empty")
    assert manifest.actual_start is manifest.actual_end is None
    assert manifest.bar_count == 0 and manifest.chunks[0].status == "EMPTY"
    assert verify(tmp_path / "empty") == manifest


def test_broker_reference_rejection_before_data(tmp_path: Path) -> None:
    with Mt5ReadOnlyProvider(FakeSdk()) as provider, pytest.raises(DiscoveryError):
        ingest(provider, Asset.BTCUSD, WINDOW, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_source_failure_message_is_not_persisted(tmp_path: Path) -> None:
    class FailedSdk(DatasetSdk):
        def copy_rates_range(self, symbol: str, start: datetime, end: datetime) -> None:
            raise DiscoveryError("synthetic-private-diagnostic")

    with Mt5ReadOnlyProvider(FailedSdk()) as provider, pytest.raises(DiscoveryError):
        ingest(provider, Asset.BTCUSD, WINDOW, tmp_path / "failed")
    for path in (tmp_path / "failed").glob("*.json"):
        assert "synthetic-private-diagnostic" not in path.read_text()


def test_demo_switch_during_history_aborts_without_publication(tmp_path: Path) -> None:
    class SwitchingSdk(DatasetSdk):
        def copy_rates_range(
            self, symbol: str, start: datetime, end: datetime
        ) -> list[dict[str, object]]:
            self.mode = 2
            return [sdk_row()]

    with Mt5ReadOnlyProvider(SwitchingSdk()) as provider, pytest.raises(DemoRequired):
        ingest(provider, Asset.BTCUSD, WINDOW, tmp_path / "aborted")
    assert (tmp_path / "aborted" / "abort.json").exists()
    assert not (tmp_path / "aborted" / "manifest.json").exists()


def test_largest_supported_decimal_round_trip(tmp_path: Path) -> None:
    price = "9999999999999999.999999999999999999"
    sample = bar(open=price, high=price, low=price, close=price)
    write_parquet(tmp_path / "large.parquet", [sample])
    assert read_parquet(tmp_path / "large.parquet") == (sample,)


def test_final_gate_requires_all_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from trading_ecosystem.datasets import verify as verifier

    dataset(tmp_path)
    monkeypatch.setattr("sys.argv", ["verify", str(tmp_path), "--require-all-assets"])
    with pytest.raises(ValueError, match="ALL_THREE_ASSET_DATASETS_REQUIRED"):
        verifier.main()


@pytest.mark.parametrize("offset", [-1, 4, 5])
def test_outside_observations_retained_and_quarantined(tmp_path: Path, offset: int) -> None:
    sdk = DatasetSdk()
    sdk.bars = [sdk_row(time=int((NOW + offset * HOUR).timestamp()))]
    target = tmp_path / "quarantine"
    with Mt5ReadOnlyProvider(sdk) as provider:
        manifest = ingest(provider, Asset.BTCUSD, WINDOW, target)
    assert verify(target) == manifest
    raw = json.loads((target / "chunk-0000.json").read_bytes())
    assert len(raw["rows"]) == 1
    assert datetime.fromisoformat(raw["rows"][0]["time"]) == NOW + offset * HOUR
    quality = json.loads((target / "quality.json").read_bytes())
    assert quality["outside_chunk_observation_count"] == 1
    exclusion = quality["quarantined_observations"][0]
    assert exclusion["classification"] == "OUTSIDE_REQUESTED_CHUNK"
    assert exclusion["source_file"] == "chunk-0000.json" and exclusion["row_index"] == 0
    assert manifest.bar_count == 0 and read_parquet(target / "normalized.parquet") == ()
    assert manifest.actual_start is manifest.actual_end is None
    assert quality["duplicate_count"] == quality["conflicting_duplicate_count"] == 0
    assert quality["missing_clock_hours"] == 4


def test_repeated_prehistory_observation_has_no_normalized_duplicates(tmp_path: Path) -> None:
    sdk = DatasetSdk()
    first = NOW + timedelta(days=62)
    sdk.bars = [sdk_row(time=int(first.timestamp()))]
    window = Window(requested_start=NOW, requested_end=NOW + timedelta(days=63))
    target = tmp_path / "history"
    with Mt5ReadOnlyProvider(sdk) as provider:
        manifest = ingest(provider, Asset.BTCUSD, window, target)
    assert verify(target) == manifest
    quality = json.loads((target / "quality.json").read_bytes())
    assert manifest.bar_count == 1 and manifest.actual_start == first
    assert manifest.actual_end == first + HOUR
    assert quality["outside_chunk_observation_count"] == 2
    assert quality["duplicate_count"] == quality["conflicting_duplicate_count"] == 0
    assert quality["gaps"][0]["classification"] == "UNCLASSIFIED_GAP"
    assert quality["gaps"][0]["missing_clock_hours"] == 62 * 24
    raws = [json.loads(path.read_bytes())["rows"] for path in sorted(target.glob("chunk-*.json"))]
    assert len(raws) == 3 and raws[0] == raws[1] == raws[2]


@pytest.mark.parametrize("asset", list(Asset))
def test_in_range_behavior_unchanged(tmp_path: Path, asset: Asset) -> None:
    sdk = DatasetSdk()
    sdk.bars = [sdk_row(), sdk_row(time=int((NOW + HOUR).timestamp()))]
    target = tmp_path / asset.value
    with Mt5ReadOnlyProvider(sdk) as provider:
        manifest = ingest(provider, asset, WINDOW, target)
    assert verify(target) == manifest and manifest.bar_count == 2
    quality = json.loads((target / "quality.json").read_bytes())
    assert quality["outside_chunk_observation_count"] == 0
    assert quality["quarantined_observations"] == []


def test_quarantine_cannot_hide_invalid_in_range_bar(tmp_path: Path) -> None:
    sdk = DatasetSdk()
    sdk.bars = [sdk_row(time=int((NOW - HOUR).timestamp())), sdk_row(high=8)]
    target = tmp_path / "failed"
    with Mt5ReadOnlyProvider(sdk) as provider, pytest.raises(DiscoveryError):
        ingest(provider, Asset.BTCUSD, WINDOW, target)
    quality = json.loads((target / "quality.json").read_bytes())
    assert quality["outside_chunk_observation_count"] == quality["invalid_ohlc_count"] == 1
    assert quality["validation_status"] == "FAIL"


def test_quarantine_does_not_bypass_timestamp_alignment(tmp_path: Path) -> None:
    sdk = DatasetSdk()
    sdk.bars = [sdk_row(time=int((NOW - HOUR + timedelta(minutes=1)).timestamp()))]
    with Mt5ReadOnlyProvider(sdk) as provider, pytest.raises(DiscoveryError):
        ingest(provider, Asset.BTCUSD, WINDOW, tmp_path / "failed")


def test_sdk_wrapper_preserves_outside_sdk_result(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from trading_ecosystem.discovery.sdk import NativeSdk

    returned = [sdk_row(time=int((NOW + 5 * HOUR).timestamp()))]
    calls = []

    def copy(
        symbol: str, timeframe: int, start: datetime, end: datetime
    ) -> list[dict[str, object]]:
        calls.append((symbol, timeframe, start, end))
        return returned

    sdk = NativeSdk.__new__(NativeSdk)
    monkeypatch.setattr(
        sdk, "_mt5", SimpleNamespace(copy_rates_range=copy, TIMEFRAME_H1=1), raising=False
    )
    result = sdk.copy_rates_range("BTCUSDm", NOW, NOW + HOUR)
    assert result == tuple(returned)
    assert calls == [("BTCUSDm", 1, NOW, NOW + HOUR)]
