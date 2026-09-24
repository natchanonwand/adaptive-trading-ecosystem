"""Two offline research exports per preserved Phase 4C source, no source mutation."""

import hashlib
import json
import time
from pathlib import Path

from trading_ecosystem.behavioral_research.contracts import ResearchConfig, canonical
from trading_ecosystem.behavioral_research.engine import compare, research
from trading_ecosystem.behavioral_research.reports import export, validate


def main() -> None:
    root = Path(".local/phase4_d/final-v2")
    if root.exists():
        raise ValueError("PRESERVE_EXISTING_RESEARCH_QUALIFICATION")
    root.mkdir(parents=True)
    evidence = {}
    results = {}
    for name in ("normal", "stress"):
        source = Path(".local/phase4_c/features-final-v2") / name
        began = time.perf_counter()
        result = research(source, ResearchConfig())
        duration = time.perf_counter() - began
        one = export(source, root / name, ResearchConfig())
        two = export(source, root / (name + "-repeat"), ResearchConfig())
        if one["content_hash"] != two["content_hash"] or one["files"] != two["files"]:
            raise ValueError("NONDETERMINISTIC_RESEARCH_EXPORT")
        validate(root / name)
        validate(root / (name + "-repeat"))
        if result["hypotheses"] or result["status"] != "SOFTWARE_VALIDATION_ONLY":
            raise ValueError("SYNTHETIC_RESEARCH_GUARD_FAILED")
        evidence[name] = dict(
            run_id=one["run_id"],
            content_hash=one["content_hash"],
            files=one["files"],
            manifest_sha256=hashlib.sha256(
                (root / name / "manifest.json").read_bytes()
            ).hexdigest(),
            n=result["fingerprint"]["n"],
            analysis_seconds=duration,
        )
        results[name] = result
    (root / "comparison.json").write_text(
        canonical(compare(results["normal"], results["stress"])) + "\n", encoding="utf-8"
    )
    (root / "qualification.json").write_text(
        json.dumps(
            dict(
                dataset_type="SYNTHETIC_QUALIFICATION",
                real_ea_research_qualification="NOT_PROVIDED",
                results=evidence,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("PASS: repeated research exports; independent rebuild and synthetic guards")


if __name__ == "__main__":
    main()
