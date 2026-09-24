"""Offline feature qualification from preserved fake Phase 4B exports only."""

import hashlib
import json
import time
import tracemalloc
from pathlib import Path

from trading_ecosystem.features.builder import build
from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.features.dataset import export
from trading_ecosystem.features.registry import CATALOG, FEATURE_SET_ID


def main() -> None:
    root = Path(".local/phase4_c/features-final-v2")
    if root.exists():
        raise ValueError("PRESERVE_EXISTING_FEATURE_QUALIFICATION")
    root.mkdir()
    results = {}
    for name in ("normal", "stress"):
        source = Path(".local/phase4_b/final") / (name + "-export")
        tracemalloc.start()
        began = time.perf_counter()
        tables, sources = build([source], BuildConfig())
        elapsed = time.perf_counter() - began
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        first = export([source], root / name, BuildConfig())
        second = export([source], root / (name + "-repeat"), BuildConfig())
        if first != second:
            raise ValueError("NONDETERMINISTIC_FEATURE_EXPORT")
        results[name] = dict(
            source=source.as_posix(),
            input_episodes=sources[0]["input_episodes"],
            market_context_rows=sources[0]["market_context_rows"],
            rows={k: len(v) for k, v in tables.items()},
            feature_count=len(CATALOG),
            build_seconds=elapsed,
            python_peak_bytes=peak,
            manifest_sha256=hashlib.sha256(
                (root / name / "manifest.json").read_bytes()
            ).hexdigest(),
        )
    (root / "qualification.json").write_text(
        json.dumps(
            dict(
                feature_set_id=FEATURE_SET_ID,
                dataset_type="SYNTHETIC_QUALIFICATION",
                real_ea_qualification="NOT_PROVIDED",
                benchmarks=results,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    print("PASS: offline build, source replay parity, two deterministic exports per session")


if __name__ == "__main__":
    main()
