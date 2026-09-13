"""Explicit verified real-data execution; routine tests never invoke this runner."""

import argparse
from pathlib import Path

from trading_ecosystem.backtests.contracts import DATA_RUN
from trading_ecosystem.backtests.datasets import load_asset
from trading_ecosystem.backtests.evidence import encoded, persist, reload_result, report_text
from trading_ecosystem.backtests.runner import COST_VERSION, research
from trading_ecosystem.benchmarks.hashing import registry_sha256, verify_artifact
from trading_ecosystem.benchmarks.registry import REGISTRY
from trading_ecosystem.domain.primitives import Asset
from trading_ecosystem.simulation.hashing import digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["datasets", "run", "verify"])
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    verify_artifact()
    source_report = Path("PHASE2B_REPORT.md").read_text(encoding="utf-8")
    loaded = [load_asset(Path("data/datasets") / DATA_RUN, asset, source_report) for asset in Asset]
    for identity, bars in loaded:
        print(f"VERIFIED {identity.asset.value}: {len(bars)} bars", flush=True)
    if args.mode == "datasets":
        return 0
    source_root = Path(__file__).parent
    code_identity = digest(
        {
            path.name: path.read_text(encoding="utf-8").replace("\r\n", "\n")
            for path in sorted(source_root.glob("*.py"))
        }
    )
    run_id = (
        "phase3_3b-"
        + digest(
            {
                "datasets": [identity for identity, _ in loaded],
                "registry": registry_sha256(),
                "cost": COST_VERSION,
                "code": code_identity,
            }
        )[:24]
    )
    root = Path("data/research/phase3_3b") / run_id
    if args.mode == "run":
        root.mkdir(parents=True, exist_ok=True)
    print("RUN " + run_id, flush=True)
    results = []
    for identity, bars in loaded:
        for definition in REGISTRY.definitions:
            path = root / (identity.asset.value + "--" + definition.benchmark_id.value + ".json")
            if path.exists():
                result = reload_result(path)
                if (
                    result["dataset_id"] != identity.dataset_id
                    or result["manifest_file_sha256"] != identity.manifest_file_sha256
                ):
                    raise ValueError("RESULT_INPUT_IDENTITY_MISMATCH")
                print("VERIFIED EXISTING " + path.name, flush=True)
            elif args.mode == "run":
                result = research(identity, bars, definition)
                persist(path, result)
                result = reload_result(path)
                print("PERSISTED VERIFIED " + path.name + " " + result["result_sha256"], flush=True)
            else:
                raise ValueError("MISSING_RESEARCH_RESULT: " + path.name)
            results.append(result)
    if len(list(root.glob("*.json"))) != 12:
        raise ValueError("EXACTLY_TWELVE_RESULTS_REQUIRED")
    # Independently reload every completed artifact after all executions.
    for path in sorted(root.glob("*.json")):
        reload_result(path)
    text = report_text(run_id, results)
    if args.report:
        if args.mode != "run":
            if Path("PHASE3_3B_REPORT.md").read_text(encoding="utf-8") != text:
                raise ValueError("TRACKED_REPORT_EVIDENCE_MISMATCH")
        else:
            Path("PHASE3_3B_REPORT.md").write_text(text, encoding="utf-8", newline="\n")
    print(encoded({"run_id": run_id, "result_count": len(results)}).decode(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
