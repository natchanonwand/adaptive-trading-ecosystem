"""Read-only completion audit for the preserved Phase 3.3B research run."""

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

from trading_ecosystem.backtests.contracts import DATA_RUN, DatasetIdentity
from trading_ecosystem.backtests.datasets import load_asset
from trading_ecosystem.backtests.evidence import reload_result, report_text
from trading_ecosystem.backtests.metrics import splits
from trading_ecosystem.backtests.runner import COST_VERSION, COSTS, SIMULATION_VERSION
from trading_ecosystem.benchmarks.hashing import registry_sha256, verify_artifact
from trading_ecosystem.benchmarks.registry import REGISTRY
from trading_ecosystem.domain.primitives import Asset
from trading_ecosystem.simulation.hashing import digest

RUN_ID = "phase3_3b-e0a03fae2bf50aadd651586b"


def verify_partials(root: Path, expected: set[str]) -> None:
    if {path.name for path in root.glob("*.json")} != expected:
        raise ValueError("EXACT_FINAL_RESULT_SET_REQUIRED")
    for partial in root.glob("*.partial"):
        final = partial.with_suffix(".json")
        if final.name not in expected or not final.is_file():
            raise ValueError("ORPHAN_PARTIAL_EVIDENCE")
        first, second = final.read_bytes(), partial.read_bytes()
        if (
            len(first) != len(second)
            or hashlib.sha256(first).digest() != hashlib.sha256(second).digest()
        ):
            raise ValueError("CONFLICTING_PARTIAL_EVIDENCE")
        if json.loads(first) != json.loads(second):
            raise ValueError("PARTIAL_SEMANTIC_MISMATCH")


def verify_identity(result: dict[str, Any], identity: DatasetIdentity, benchmark: str) -> None:
    for key, value in identity.model_dump(mode="json").items():
        if result.get(key) != value:
            raise ValueError("RESULT_DATASET_PROVENANCE_MISMATCH: " + key)
    expected = {
        "benchmark_id": benchmark,
        "simulation_model_version": SIMULATION_VERSION,
        "cost_model_version": COST_VERSION,
        "split_policy": "ASSET_LOCAL_CHRONOLOGICAL_SPLIT",
        "spread_handling": "UNMODELED",
        "research_schema_version": "phase3.3b-v0.1.0",
        "costs": COSTS.model_dump(mode="json"),
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise ValueError("RESULT_RESEARCH_POLICY_MISMATCH: " + key)
    for record in result["records"]:
        for key in identity.model_fields:
            if record.get(key) != result[key]:
                raise ValueError("EPISODE_DATASET_PROVENANCE_MISMATCH: " + key)
        for key in (
            "benchmark_id",
            "benchmark_definition_hash",
            "simulation_model_version",
            "cost_model_version",
        ):
            if record[key] != result[key]:
                raise ValueError("EPISODE_RESEARCH_PROVENANCE_MISMATCH: " + key)


def main() -> int:
    verify_artifact()
    source = Path("src/trading_ecosystem/backtests")
    tree = ast.parse((source / "runner.py").read_text(encoding="utf-8"))
    count = sum(
        isinstance(key, ast.Constant) and key.value == "tick_assumption"
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for key in node.keys
    )
    if count != 1:
        raise ValueError("TICK_ASSUMPTION_KEY_COUNT")
    root = Path("data/research/phase3_3b") / RUN_ID
    expected = {
        asset.value + "--" + definition.benchmark_id.value + ".json"
        for asset in Asset
        for definition in REGISTRY.definitions
    }
    verify_partials(root, expected)
    print("PASS exact 12 finals and all retained partial pairs", flush=True)
    loaded = []
    results = []
    report = Path("PHASE2B_REPORT.md").read_text(encoding="utf-8")
    for asset in Asset:
        identity, bars = load_asset(Path("data/datasets") / DATA_RUN, asset, report)
        loaded.append(identity)
        boundaries = [item.model_dump(mode="json") for item in splits(bars)]
        for definition in REGISTRY.definitions:
            path = root / (asset.value + "--" + definition.benchmark_id.value + ".json")
            result = reload_result(path)
            verify_identity(result, identity, definition.benchmark_id.value)
            if result["splits"] != boundaries:
                raise ValueError("FROZEN_SPLIT_BOUNDARIES_MISMATCH")
            results.append(result)
        print("PASS frozen dataset, four results and split boundaries: " + asset.value, flush=True)
    code_identity = digest(
        {
            path.name: path.read_text(encoding="utf-8").replace("\r\n", "\n")
            for path in sorted(source.glob("*.py"))
        }
    )
    actual_id = (
        "phase3_3b-"
        + digest(
            {
                "datasets": loaded,
                "registry": registry_sha256(),
                "cost": COST_VERSION,
                "code": code_identity,
            }
        )[:24]
    )
    if actual_id != RUN_ID:
        raise ValueError("PRESERVED_RUN_IDENTITY_MISMATCH")
    if Path("PHASE3_3B_REPORT.md").read_text(encoding="utf-8") != report_text(RUN_ID, results):
        raise ValueError("REPORT_RESULT_MISMATCH")
    print(
        "PASS preserved run identity, all 12 results, exact report; no simulations rerun",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
