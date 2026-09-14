"""Verified episode-only inputs and deterministic layered output identities."""

from datetime import timedelta
from pathlib import Path
from typing import Any

from trading_ecosystem.backtests.evidence import encoded, reload_result, report_text
from trading_ecosystem.benchmarks.hashing import registry_sha256, verify_artifact
from trading_ecosystem.benchmarks.registry import REGISTRY
from trading_ecosystem.datasets.contracts import Manifest
from trading_ecosystem.datasets.storage import file_hash, object_hash, read_json
from trading_ecosystem.portfolios.accounting import r_analysis
from trading_ecosystem.portfolios.contracts import (
    AGGREGATION_VERSION,
    ASSET_ORDER,
    INPUT_RUN,
    SCENARIO,
    Episode,
    Interval,
)
from trading_ecosystem.portfolios.events import common_interval
from trading_ecosystem.portfolios.synthetic import synthetic
from trading_ecosystem.simulation.hashing import canonical_value, digest


def validate_input_set(results: list[dict[str, Any]]) -> None:
    expected = {
        (asset.value, definition.benchmark_id.value)
        for asset in ASSET_ORDER
        for definition in REGISTRY.definitions
    }
    keys = [(item["asset"], item["benchmark_id"]) for item in results]
    if len(keys) != 12 or len(set(keys)) != 12 or set(keys) != expected:
        raise ValueError("EXACT_TWELVE_UNIQUE_FROZEN_INPUTS_REQUIRED")
    if (
        len({item["registry_sha256"] for item in results}) != 1
        or results[0]["registry_sha256"] != registry_sha256()
    ):
        raise ValueError("FROZEN_REGISTRY_MISMATCH")


def load_inputs() -> tuple[list[dict[str, Any]], Interval]:
    verify_artifact()
    root = Path("data/research/phase3_3b") / INPUT_RUN
    expected = {
        asset.value + "--" + item.benchmark_id.value + ".json"
        for asset in ASSET_ORDER
        for item in REGISTRY.definitions
    }
    if {path.name for path in root.glob("*.json")} != expected:
        raise ValueError("FROZEN_INPUT_FILE_SET_MISMATCH")
    results = [
        reload_result(root / (asset.value + "--" + item.benchmark_id.value + ".json"))
        for asset in ASSET_ORDER
        for item in REGISTRY.definitions
    ]
    validate_input_set(results)
    if Path("PHASE3_3B_REPORT.md").read_text(encoding="utf-8") != report_text(INPUT_RUN, results):
        raise ValueError("FROZEN_INPUT_REPORT_MISMATCH")
    ranges = []
    for result in results[::4]:
        folder = Path("data/datasets") / result["dataset_run"] / result["asset"]
        manifest = Manifest.model_validate(read_json(folder / "manifest.json"))
        if manifest.manifest_hash != object_hash(
            manifest.model_dump(mode="json", exclude={"manifest_hash"})
        ):
            raise ValueError("MANIFEST_CONTENT_MISMATCH")
        if (
            manifest.dataset_id != result["dataset_id"]
            or manifest.manifest_hash != result["dataset_manifest_hash"]
            or file_hash(folder / "manifest.json") != result["manifest_file_sha256"]
            or file_hash(folder / "normalized.parquet") != result["parquet_sha256"]
        ):
            raise ValueError("FROZEN_DATASET_IDENTITY_MISMATCH")
        if manifest.actual_start is None or manifest.actual_end is None:
            raise ValueError("EMPTY_DATASET")
        ranges.append(
            Interval(start=manifest.actual_start + timedelta(hours=1), end=manifest.actual_end)
        )
    return results, common_interval(tuple(ranges))


def extract(result: dict[str, Any]) -> tuple[Episode, ...]:
    episodes = []
    for record in result["records"]:
        if record["entry_time"] is None:
            continue
        trace = record["simulation_result"]["events"]
        entries = [event for event in trace if event["entry"] is not None]
        exits = [event for event in trace if event["exit"] is not None]
        if len(entries) != 1 or len(exits) != (1 if record["exit_time"] else 0):
            raise ValueError("FROZEN_EPISODE_EVENT_MISMATCH")
        episodes.append(
            Episode(
                episode_id=digest(record),
                asset=record["asset"],
                benchmark_id=record["benchmark_id"],
                signal_time=record["signal_time"],
                entry_time=record["entry_time"],
                exit_time=record["exit_time"],
                gross_price_R=record["gross_price_R"],
                entry_priority=entries[0]["kind"],
                entry_sequence=entries[0]["sequence"],
                exit_priority=exits[0]["kind"] if exits else None,
                exit_sequence=exits[0]["sequence"] if exits else None,
            )
        )
    return tuple(episodes)


def signed(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = canonical_value(payload)
    if not isinstance(normalized, dict):
        raise TypeError("RESULT_OBJECT_REQUIRED")
    return {**normalized, "result_sha256": digest(normalized)}


def build(results: list[dict[str, Any]], interval: Interval) -> list[dict[str, Any]]:
    validate_input_set(results)
    outputs: list[dict[str, Any]] = []
    first, second = interval.cuts()
    for index, definition in enumerate(REGISTRY.definitions, 1):
        members = [
            next(
                item
                for item in results
                if item["asset"] == asset.value
                and item["benchmark_id"] == definition.benchmark_id.value
            )
            for asset in ASSET_ORDER
        ]
        all_episodes = tuple(episode for item in members for episode in extract(item))
        selected = tuple(
            item for item in all_episodes if interval.start <= item.signal_time <= interval.end
        )
        provenance = {
            "research_schema_version": "phase3.3c-v0.1.0",
            "input_run_id": INPUT_RUN,
            "portfolio_id": f"PORTFOLIO_B{index:02d}",
            "benchmark_id": definition.benchmark_id,
            "benchmark_hash": members[0]["benchmark_definition_hash"],
            "input_result_hashes": [item["result_sha256"] for item in members],
            "registry_sha256": registry_sha256(),
            "common_interval": interval,
            "calendar_splits": {
                "Development": [interval.start, first],
                "Validation": [first, second],
                "Locked OOS": [second, interval.end],
            },
            "aggregation_model_version": AGGREGATION_VERSION,
            "research_classification": "EXPLORATORY_RESEARCH_ONLY",
            "qualification_eligible": False,
            "cost_model_version": "COST_MODEL_BASELINE_V0",
            "spread": "UNMODELED",
            "slippage": "0 assumption",
            "commission": "0 assumption",
            "financing": "0 assumption",
            "pre_common_excluded": {
                asset.value: sum(
                    item.asset == asset and item.signal_time < interval.start
                    for item in all_episodes
                )
                for asset in ASSET_ORDER
            },
            "post_common_excluded": sum(item.signal_time > interval.end for item in all_episodes),
        }
        primary = signed(
            {**provenance, "layer": "PRIMARY_R_SPACE", "analysis": r_analysis(selected, interval)}
        )
        secondary = signed(
            {
                **provenance,
                "layer": "SECONDARY_SYNTHETIC_EQUITY",
                "scenario": SCENARIO,
                "analysis": synthetic(selected, interval),
            }
        )
        outputs.extend((primary, secondary))
    return outputs


def write_exclusive(path: Path, result: dict[str, Any]) -> None:
    raw = encoded(result)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("EXISTING_PORTFOLIO_EVIDENCE_CONFLICT")
        return
    with path.open("xb") as stream:
        stream.write(raw)


def verify_outputs(root: Path, expected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {item["portfolio_id"] + "--" + item["layer"] + ".json" for item in expected}
    if {path.name for path in root.iterdir()} != names or len(names) != 8:
        raise ValueError("EXACT_FOUR_PORTFOLIOS_TWO_LAYERS_REQUIRED")
    reloaded = []
    for item in expected:
        path = root / (item["portfolio_id"] + "--" + item["layer"] + ".json")
        result = read_json(path)
        if result["result_sha256"] != digest(
            {key: value for key, value in result.items() if key != "result_sha256"}
        ):
            raise ValueError("PORTFOLIO_RESULT_HASH_MISMATCH")
        if result != item or path.read_bytes() != encoded(item):
            raise ValueError("DETERMINISTIC_AGGREGATION_REPLAY_MISMATCH")
        reloaded.append(result)
    return reloaded
