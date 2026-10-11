"""Phase 5C.1 scope, frozen lineage and strict historical evidence verification."""

import hashlib
import json
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, text

BASE = "efdf23b4c41fab1f990b414e222d7bf4e75b2812"  # pragma: allowlist secret
RESEARCH = "f6e3621973c55bc479c7be0b9d8833de0436c6f4"  # pragma: allowlist secret
ALLOWED = {
    "alembic-campaigns.ini",
    "migrations/campaigns/__init__.py",
    "migrations/campaigns/env.py",
    "migrations/campaigns/versions/__init__.py",
    "migrations/campaigns/versions/0001_campaigns.py",
    "src/trading_ecosystem/experiments/campaigns.py",
    "src/trading_ecosystem/experiments/campaign_store.py",
    "src/trading_ecosystem/experiments/campaign_runner.py",
    "src/trading_ecosystem/experiments/campaign_api.py",
    "src/trading_ecosystem/experiments/baseline_boundary.py",
    "src/trading_ecosystem/workbench/__main__.py",
    "dashboard/src/workbench/CampaignPanel.tsx",
    "dashboard/src/workbench/ExperimentsPanel.tsx",
    "dashboard/tests/campaigns.test.tsx",
    "tests/test_campaigns.py",
    "tests/integration/test_experiment_campaigns.py",
    "scripts/verify_phase5_c1.py",
    "scripts/verify_phase5_c1.ps1",
    "docs/PHASE5_C1_CONTROLLED_RUNNER.md",
    "PHASE5_C1_REPORT.md",
}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    for ref in ("HEAD", "origin/main", "ui-retro-v0.2.0^{commit}"):
        if git("rev-parse", ref) != BASE:
            raise ValueError("FROZEN_UI_BASELINE_CHANGED")
    if git("rev-parse", "phase5c-contract-v0.1.0^{commit}") != RESEARCH:
        raise ValueError("FROZEN_RESEARCH_BASELINE_CHANGED")
    tags = json.loads(Path(".local/phase5_c1/tags-before.json").read_text(encoding="utf-8-sig"))
    if git("show-ref", "--tags").splitlines() != tags:
        raise ValueError("PRIOR_TAG_CHANGED")
    changed = set(git("diff", "--name-only", BASE).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    if changed - ALLOWED:
        raise ValueError("OUTSIDE_PHASE5_C1_SCOPE: " + repr(sorted(changed - ALLOWED)))
    for label, path, expected in (
        ("frozen", ".local/phase4_e/preserved-evidence.json", 1044),
        ("historical", ".local/phase5_c0/preserved-before.json", 1621),
    ):
        records = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if len(records) != expected:
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
            exists = conn.execute(
                text("SELECT to_regclass('workbench.experiment_campaigns')")
            ).scalar_one()
            if (
                exists
                and conn.execute(
                    text("SELECT count(*) FROM workbench.experiment_campaigns")
                ).scalar_one()
            ):
                raise ValueError("UNAUTHORIZED_REAL_CAMPAIGN_RECORDS")
    finally:
        engine.dispose()
    for path in (".local/phase5_c1/review.png", "test-results/phase5_c1.xml", "dashboard/dist"):
        git("check-ignore", "--no-index", path)
    git("diff", "--check")
    print("PASS: Phase 5C.1 scope, frozen contracts/UI/tags, ignored outputs; 0 real campaigns")


if __name__ == "__main__":
    main()
