from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.datasets.test_datasets import dataset
from tests.research.test_indicators import bars
from trading_ecosystem.backtests.contracts import EXPECTED_COUNTS, DatasetIdentity, SplitName
from trading_ecosystem.backtests.datasets import pins, verify_loaded
from trading_ecosystem.backtests.evidence import encoded, persist, reload_result, verify_result
from trading_ecosystem.backtests.metrics import split_at, splits, summarize
from trading_ecosystem.backtests.runner import research
from trading_ecosystem.backtests.signals import signals
from trading_ecosystem.benchmarks.contracts import BenchmarkId, ResearchDecision
from trading_ecosystem.benchmarks.hashing import verify_artifact
from trading_ecosystem.benchmarks.registry import get_definition
from trading_ecosystem.datasets.contracts import Manifest
from trading_ecosystem.datasets.storage import file_hash, read_json, read_parquet
from trading_ecosystem.domain.primitives import Asset
from trading_ecosystem.simulation.hashing import digest


def identity() -> DatasetIdentity:
    return DatasetIdentity(
        asset=Asset.BTCUSD,
        dataset_id="synthetic-kernel",
        dataset_manifest_hash="0" * 64,
        manifest_file_sha256="1" * 64,
        parquet_sha256="2" * 64,
        metadata_sha256="0" * 64,
        tick_size=D("0.01"),
    )


def rising(count: int = 270) -> tuple[Any, ...]:
    return bars(tuple(str(100 + index) for index in range(count)))


@pytest.mark.parametrize(
    "benchmark,warmup", [(BenchmarkId.B01, 250), (BenchmarkId.B03, 21), (BenchmarkId.B04, 56)]
)
def test_frozen_warmup_and_strict_channel_entries(benchmark: BenchmarkId, warmup: int) -> None:
    decisions = signals(rising(), get_definition(benchmark))
    assert all(item == ResearchDecision.UNAVAILABLE for item in decisions[: warmup - 1])
    assert decisions[warmup - 1] == ResearchDecision.ENTRY_ELIGIBLE
    assert decisions == signals(rising(), get_definition(benchmark))


def test_b02_cross_not_persistent_state() -> None:
    definition = get_definition(BenchmarkId.B02)
    persistent = signals(rising(), definition)
    assert ResearchDecision.ENTRY_ELIGIBLE not in persistent
    values = bars(tuple(str(1000 - index if index < 210 else 2000 + index) for index in range(300)))
    decisions = signals(values, definition)
    assert decisions.count(ResearchDecision.ENTRY_ELIGIBLE) == 1
    assert all(value == ResearchDecision.HOLD_OR_NO_ACTION for value in decisions[-20:])


@pytest.mark.parametrize("benchmark", [BenchmarkId.B03, BenchmarkId.B04])
def test_channel_exit_and_equality(benchmark: BenchmarkId) -> None:
    values = bars(tuple(["100"] * 60 + ["99"]))
    decisions = signals(values, get_definition(benchmark))
    assert decisions[-2] == ResearchDecision.HOLD_OR_NO_ACTION
    assert decisions[-1] == ResearchDecision.EXIT_ELIGIBLE


@pytest.mark.parametrize("benchmark", list(BenchmarkId))
def test_future_mutation_preserves_prior_signals(benchmark: BenchmarkId) -> None:
    original = rising(280)
    changed = original[:260] + tuple(
        bar.model_copy(update={"open": D("1"), "close": D("1"), "high": D("2"), "low": D("0.5")})
        for bar in original[260:]
    )
    assert (
        signals(original, get_definition(benchmark))[:260]
        == signals(changed, get_definition(benchmark))[:260]
    )


@pytest.mark.parametrize("size,edges", [(5, (3, 4, 5)), (11, (6, 8, 11)), (270, (162, 216, 270))])
def test_asset_local_split_indices_and_decision_boundaries(
    size: int, edges: tuple[int, int, int]
) -> None:
    observations = rising(size)
    result = splits(observations)
    assert tuple(item.end_index_exclusive for item in result) == edges
    assert result == splits(observations)
    assert result[0].first_decision_time == observations[0].close_time
    assert result[1].first_decision_time == observations[edges[0]].close_time
    assert split_at(edges[0] - 1, result) == SplitName.DEVELOPMENT
    assert split_at(edges[0], result) == SplitName.VALIDATION
    assert split_at(edges[1], result) == SplitName.LOCKED_OOS


def test_single_episode_no_same_bar_reentry_actual_fill_target_and_boundary() -> None:
    result = research(identity(), rising(270), get_definition(BenchmarkId.B01))
    records = result["records"]
    assert records and result["metrics"]["filled_entries"] == len(records)
    last_end = -1
    for record in records:
        assert record["signal_index"] > last_end
        last_end = record["signal_index"] + max(
            event["bar_index"] for event in record["simulation_result"]["events"]
        )
        entry, stop = D(record["entry_fill"]), D(record["fixed_stop"])
        assert D(record["take_profit"]) >= entry + 2 * (entry - stop)
        assert record["split"] == split_at(record["signal_index"], splits(rising(270))).value
    # A truncated live episode is disclosed, not forced into completed metrics.
    boundary = research(identity(), rising(251), get_definition(BenchmarkId.B01))
    assert boundary["metrics"]["open_at_boundary_count"] == 1
    assert boundary["metrics"]["completed_episodes"] == 0
    assert boundary["records"][0]["exit_reason"] is None
    assert boundary["records"][0]["status"] == "OPEN_AT_EVALUATION_BOUNDARY"


def test_cross_split_and_gap_accounting() -> None:
    observations = bars(
        tuple(str(100 + index) for index in range(100)),
        offsets=tuple(index if index < 60 else index + 5 for index in range(100)),
    )
    result = research(identity(), observations, get_definition(BenchmarkId.B04))
    filled = [record for record in result["records"] if record["entry_time"]]
    assert result["metrics"]["cross_split_episode_count"] == sum(
        record["cross_split"] for record in filled
    )
    assert result["metrics"]["cross_split_episode_count"] > 0
    assert result["metrics"]["gap_entry_count"] == sum(record["gap_entry"] for record in filled)
    assert (
        sum(metrics["completed_episodes"] for metrics in result["split_metrics"].values())
        == result["metrics"]["completed_episodes"]
    )
    assert (
        sum(metrics["filled_entries"] for metrics in result["split_metrics"].values())
        == result["metrics"]["filled_entries"]
    )


def metric_record(value: str, **updates: object) -> dict[str, Any]:
    return {
        "status": "COMPLETED",
        "entry_time": "synthetic",
        "gross_price_R": value,
        "holding_observed_bars": 2,
        "holding_clock_hours": "1",
        "intrabar_ambiguous": False,
        "gap_entry": False,
        "gap_exit": False,
        "preceded_by_gap_at_signal": False,
        "cross_split": False,
        **updates,
    }


def test_metric_arithmetic_streaks_and_diagnostics() -> None:
    records = [metric_record(value) for value in ["2", "1", "-1", "-2", "0", "3"]]
    records[0].update(
        intrabar_ambiguous=True,
        gap_entry=True,
        gap_exit=True,
        preceded_by_gap_at_signal=True,
        cross_split=True,
    )
    result = summarize(records, 12)
    assert result["wins"] == 3 and result["losses"] == 2 and result["break_even_episodes"] == 1
    assert result["win_rate"] == D("0.5") and result["gross_cumulative_R"] == 3
    assert result["mean_gross_R"] == D("0.5") and result["median_gross_R"] == D("0.5")
    assert result["average_winning_R"] == 2 and result["average_losing_R"] == D("-1.5")
    assert result["profit_factor_R"]["value"] == 2
    assert result["maximum_winning_streak"] == result["maximum_losing_streak"] == 2
    assert result["average_holding_observed_bars"] == result["median_holding_observed_bars"] == 2
    assert result["average_holding_clock_hours"] == 1
    for field in [
        "intrabar_ambiguous_count",
        "gap_entry_count",
        "gap_exit_count",
        "gap_adjacent_signal_count",
        "cross_split_episode_count",
    ]:
        assert result[field] == 1


@pytest.mark.parametrize(
    "values,state,value",
    [
        ([], "UNDEFINED", None),
        (["0"], "UNDEFINED", None),
        (["2"], "POSITIVE_INFINITY", None),
        (["-1"], "FINITE", D(0)),
    ],
)
def test_profit_factor_denominator_policy(values: list[str], state: str, value: D | None) -> None:
    result = summarize([metric_record(item) for item in values], 0)
    assert result["profit_factor_R"]["state"] == state
    assert result["profit_factor_R"]["value"] == value


def test_deterministic_replay_and_exclusive_evidence(tmp_path: Path) -> None:
    definition = get_definition(BenchmarkId.B03)
    result = research(identity(), rising(70), definition)
    with localcontext() as context:
        context.prec = 6
        assert research(identity(), rising(70), definition) == result
    verify_result(result)
    path = tmp_path / "result.json"
    persist(path, result)
    before = path.read_bytes()
    assert reload_result(path) == result
    persist(path, result)
    assert path.read_bytes() == before
    changed = {**result, "result_sha256": "0" * 64}
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        verify_result(changed)
    changed = {**result, "dataset_id": "different"}
    changed["result_sha256"] = digest(
        {key: value for key, value in changed.items() if key != "result_sha256"}
    )
    with pytest.raises(ValueError, match="EXISTING_VERIFIED_RESULT_CONFLICT"):
        persist(path, changed)
    partial_path = tmp_path / "partial.json"
    partial_path.with_suffix(".partial").write_bytes(b"preserve incomplete bytes")
    with pytest.raises(ValueError, match="PARTIAL_EVIDENCE_CONFLICT"):
        persist(partial_path, result)
    assert partial_path.with_suffix(".partial").read_bytes() == b"preserve incomplete bytes"
    assert encoded(result) == before


def test_dataset_identity_verification_with_small_synthetic_ingestion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = dataset(tmp_path)
    manifest = Manifest.model_validate(read_json(directory / "manifest.json"))
    observations = read_parquet(directory / "normalized.parquet")
    monkeypatch.setitem(EXPECTED_COUNTS, Asset.BTCUSD, 2)
    parquet = file_hash(directory / "normalized.parquet")
    manifest_file = file_hash(directory / "manifest.json")
    expected = (manifest.dataset_id, parquet, manifest.manifest_hash)
    verify_loaded(manifest, observations, expected, parquet, manifest_file)
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        verify_loaded(
            manifest,
            observations,
            ("0" * 64, parquet, manifest.manifest_hash),
            parquet,
            manifest_file,
        )
    with pytest.raises(ValueError, match="CHRONOLOGY"):
        verify_loaded(manifest, tuple(reversed(observations)), expected, parquet, manifest_file)
    with pytest.raises(ValueError, match="CHRONOLOGY"):
        verify_loaded(
            manifest, (observations[0], observations[0]), expected, parquet, manifest_file
        )
    with pytest.raises(ValueError, match="MANIFEST_PIN"):
        verify_loaded(
            manifest, observations, (manifest.dataset_id, parquet, "0" * 64), parquet, manifest_file
        )


def test_frozen_registry_and_report_pin_parser() -> None:
    verify_artifact()
    report = Path("PHASE2B_REPORT.md").read_text(encoding="utf-8")
    for asset in Asset:
        assert all(len(value) == 64 for value in pins(report, asset))
    with pytest.raises(ValidationError):
        get_definition(BenchmarkId.B01).model_copy(update={"required_observations": 249})
