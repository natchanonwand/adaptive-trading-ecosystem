"""Preserve all pre-registration rows and frozen evidence during qualification."""

import hashlib
import json
import subprocess
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select

from trading_ecosystem.experiments import campaign_store, store
from trading_ecosystem.experiments.authorization import review
from trading_ecosystem.tester import publication, readiness
from trading_ecosystem.tester import store as baseline
from trading_ecosystem.workbench import store as onboarding


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    frozen = json.loads(Path(".local/phase5_c2b/freeze-before.json").read_bytes())
    head = git("rev-parse", "phase5c-prereg-v0.1.0^{commit}")
    if head != git("rev-parse", "HEAD") or head != git("rev-parse", "origin/main"):
        raise ValueError("BASELINE_CHANGED")
    expected_tags = set(frozen["tags"]) | {
        "46ff1b4f11c9d259d2326c27fe5cbd7b94e4c817 refs/tags/phase5c-prereg-v0.1.0"
    }
    if set(git("show-ref", "--tags").splitlines()) != expected_tags:
        raise ValueError("TAGS_CHANGED")
    for path, expected in frozen["files"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("EVIDENCE_CHANGED: " + path)
    for path, expected in frozen["tracked"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("FROZEN_PREREGISTRATION_SOURCE_CHANGED: " + path)
    url = json.loads(Path(".local/phase4_a/runtime.json").read_text(encoding="utf-8-sig"))[
        "database_url"
    ]
    engine = create_engine(url)
    tables = [
        onboarding.projects,
        onboarding.candidates,
        onboarding.artifacts,
        readiness.authorizations,
        readiness.configurations,
        baseline.runs,
        baseline.results,
        publication.publications,
        store.records,
        campaign_store.records,
    ]
    try:
        with engine.connect() as conn:
            current = {
                t.name: [dict(r) for r in conn.execute(select(t).order_by(t.c.id)).mappings()]
                for t in tables
            }
            if json.loads(json.dumps(current, default=str)) != frozen["database"]:
                raise ValueError("RESEARCH_DATABASE_CHANGED")
            value = review(
                conn,
                UUID("acc5933d-3135-524e-a6af-17ae7f77eb1e"),
                Path(".local/artifacts/research_projects"),
                Path(".local/phase5_b"),
            )
            if value != frozen["review"]:
                raise ValueError("AUTHORIZATION_CHANGED")
    finally:
        engine.dispose()
    allowed = {
        "src/trading_ecosystem/tester/portable_qualification.py",
        "tests/test_portable_qualification.py",
        "scripts/verify_phase5_c2c.py",
        "scripts/verify_phase5_c2c.ps1",
        "PHASE5_C2C_REPORT.md",
    }
    changed = set(git("diff", "--name-only", "HEAD").splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    if changed - allowed:
        raise ValueError("SCOPE_CHANGED")
    git("check-ignore", "--no-index", ".local/phase5_c2c/probe/terminal/terminal64.exe")
    git("diff", "--check")
    print("PASS: 1044 frozen + 1621 historical files, prior probes and all research rows unchanged")
    print("PASS: campaign 0/11; Gold Scalper 1; NOT_AUTHORIZED; START disabled; OOS sealed")


if __name__ == "__main__":
    main()
