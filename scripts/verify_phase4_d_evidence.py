"""Preservation and independent offline research artifact verification."""

import hashlib
import json
from pathlib import Path

from trading_ecosystem.behavioral_research.contracts import ResearchConfig
from trading_ecosystem.behavioral_research.engine import compare, research
from trading_ecosystem.behavioral_research.reports import validate


def main() -> None:
    baseline = json.loads(
        Path(".local/phase4_d/preserved-evidence.json").read_text(encoding="utf-8-sig")
    )
    for name, expected in baseline.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError("PRESERVED_EVIDENCE_CHANGED: " + name)
    sizes = {
        label: sum(name.startswith(prefix) for name in baseline)
        for label, prefix in (
            ("historical", ("data/datasets/", "data/research/")),
            ("phase4b", (".local/phase4_b/",)),
            ("phase4c", (".local/phase4_c/",)),
        )
    }
    if sizes != dict(historical=874, phase4b=53, phase4c=57):
        raise ValueError("PRESERVATION_BASELINE_SCOPE_MISMATCH")
    root = Path(".local/phase4_d/final-v2")
    qualification = json.loads((root / "qualification.json").read_bytes())
    if set(qualification["results"]) != {"normal", "stress"}:
        raise ValueError("QUALIFICATION_RESULT_SET_MISMATCH")
    results = {}
    for name, expected in qualification["results"].items():
        first, second = validate(root / name), validate(root / (name + "-repeat"))
        if (
            first["files"] != second["files"]
            or first["content_hash"] != second["content_hash"]
            or first["content_hash"] != expected["content_hash"]
            or first["files"] != expected["files"]
            or first["run_id"] != expected["run_id"]
            or hashlib.sha256((root / name / "manifest.json").read_bytes()).hexdigest()
            != expected["manifest_sha256"]
        ):
            raise ValueError("QUALIFICATION_HASH_MISMATCH")
        result = research(
            Path(first["dataset_path"]), ResearchConfig.model_validate(first["research_config"])
        )
        if result["status"] != "SOFTWARE_VALIDATION_ONLY" or result["hypotheses"]:
            raise ValueError("SYNTHETIC_RESEARCH_CONCLUSION")
        results[name] = result
    if json.loads((root / "comparison.json").read_bytes()) != compare(
        results["normal"], results["stress"]
    ):
        raise ValueError("RESEARCH_COMPARISON_MISMATCH")
    print(f"PASS: preserved evidence unchanged {sizes}")
    print("PASS: research artifacts and comparison independently rebuilt")
    print("REAL_EA_RESEARCH_QUALIFICATION: NOT PROVIDED")


if __name__ == "__main__":
    main()
