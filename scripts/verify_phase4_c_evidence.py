"""Verify Phase 4C exports and unchanged frozen evidence without simulations."""

import hashlib
import json
from pathlib import Path

from trading_ecosystem.features.dataset import validate
from trading_ecosystem.features.registry import CATALOG, FEATURE_SET_ID


def main() -> None:
    baseline = json.loads(Path(".local/phase4_c/preserved-evidence.json").read_text())
    for name, expected in baseline.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError("PRESERVED_EVIDENCE_CHANGED: " + name)
    frozen = sum(name.startswith(("data/datasets/", "data/research/")) for name in baseline)
    if frozen != 874:
        raise ValueError("EXPECTED_874_FROZEN_FILES")
    root = Path(".local/phase4_c/features-final-v2")
    evidence = json.loads((root / "qualification.json").read_text())
    if evidence["feature_set_id"] != FEATURE_SET_ID:
        raise ValueError("QUALIFICATION_FEATURE_SET_MISMATCH")
    if json.loads(Path("reports/feature_registry.json").read_text()) != [
        d.model_dump(mode="json") for d in CATALOG
    ]:
        raise ValueError("FEATURE_CATALOG_MISMATCH")
    for name, benchmark in evidence["benchmarks"].items():
        if name not in ("normal", "stress"):
            raise ValueError("UNKNOWN_QUALIFICATION_DATASET")
        first = validate(root / name)
        second = validate(root / (name + "-repeat"))
        if (
            first != second
            or hashlib.sha256((root / name / "manifest.json").read_bytes()).hexdigest()
            != benchmark["manifest_sha256"]
        ):
            raise ValueError("FEATURE_QUALIFICATION_HASH_MISMATCH")
    print(f"PASS: {frozen} historical files and {len(baseline) - frozen} Phase 4B files unchanged")
    print("PASS: Phase 4C canonical rebuild, raw replay, catalog and source hashes")
    print("REAL_EA_FEATURE_QUALIFICATION: NOT PROVIDED")


if __name__ == "__main__":
    main()
