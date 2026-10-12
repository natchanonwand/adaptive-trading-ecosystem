"""UI-2 presentation scope; strict frozen research/history and no real campaign."""

import hashlib
import json
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, text

BASE = "928ef6fbddccd999f79cbb19cbcb3ba99438457f"  # pragma: allowlist secret
UI_BASE = "efdf23b4c41fab1f990b414e222d7bf4e75b2812"  # pragma: allowlist secret
RESEARCH = "f6e3621973c55bc479c7be0b9d8833de0436c6f4"  # pragma: allowlist secret
ALLOWED = {
    "dashboard/src/workbench/ExperimentLab.tsx",
    "dashboard/src/workbench/experiment-lab.css",
    "dashboard/src/workbench/ExperimentsPanel.tsx",
    "dashboard/src/workbench/CampaignPanel.tsx",
    "dashboard/tests/experiment-lab.test.tsx",
    "dashboard/tests/experiments.test.tsx",
    "dashboard/tests/campaigns.test.tsx",
    "docs/UI2_EXPERIMENT_LAB.md",
    "UI2_REPORT.md",
    "scripts/verify_ui2.py",
    "scripts/verify_ui2.ps1",
}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    for ref in ("HEAD", "origin/main", "phase5c-runner-v0.1.0^{commit}"):
        if git("rev-parse", ref) != BASE:
            raise ValueError("FROZEN_RUNNER_BASELINE_CHANGED")
    for ref, expected in (
        ("ui-retro-v0.2.0^{commit}", UI_BASE),
        ("phase5c-contract-v0.1.0^{commit}", RESEARCH),
    ):
        if git("rev-parse", ref) != expected:
            raise ValueError("FROZEN_BASELINE_CHANGED")
    tags = json.loads(Path(".local/ui2/tags-before.json").read_text(encoding="utf-8-sig"))
    if git("show-ref", "--tags").splitlines() != tags:
        raise ValueError("PRIOR_TAG_CHANGED")
    changed = set(git("diff", "--name-only", BASE).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    if changed - ALLOWED:
        raise ValueError("OUTSIDE_UI2_SCOPE: " + repr(sorted(changed - ALLOWED)))
    for label, path, expected_count in (
        ("frozen", ".local/phase4_e/preserved-evidence.json", 1044),
        ("historical", ".local/phase5_c0/preserved-before.json", 1621),
    ):
        records = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if len(records) != expected_count:
            raise ValueError("EVIDENCE_INVENTORY_CHANGED")
        for name, sha in records.items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != sha.lower():
                raise ValueError("EVIDENCE_CHANGED: " + name)
        print(f"PASS: {len(records)} {label} evidence files byte-identical")
    url = json.loads(Path(".local/phase4_a/runtime.json").read_text(encoding="utf-8-sig"))[
        "database_url"
    ]
    engine = create_engine(url, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT count(*) FROM workbench.experiment_campaigns")).scalar():
                raise ValueError("REAL_CAMPAIGN_CREATED")
    finally:
        engine.dispose()
    git("check-ignore", "--no-index", ".local/ui2/review.png", "dashboard/dist")
    git("diff", "--check")
    print("PASS: UI-2 scope; Phase 5B/5C.0/5C.1 backend, contracts, tests and prior UI preserved")


if __name__ == "__main__":
    main()
