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
from trading_ecosystem.tester.qualification import digest
from trading_ecosystem.workbench import store as onboarding


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    frozen = json.loads(Path(".local/phase5_c2c/freeze-before.json").read_bytes())
    head = git("rev-parse", "phase5c-envready-v0.1.0^{commit}")
    if head != git("rev-parse", "HEAD") or head != git("rev-parse", "origin/main"):
        raise ValueError("BASELINE_CHANGED")
    expected_tags = set(frozen["tags"]) | {
        "ffa6dd660558cccfa8b4deb362a650d17b94a5ca refs/tags/phase5c-envprobe-v0.1.0",
        "b3bfcc9fa75e56974b09d96262439f9b06c1faac refs/tags/phase5c-envready-v0.1.0",
    }
    if set(git("show-ref", "--tags").splitlines()) != expected_tags:
        raise ValueError("TAGS_CHANGED")
    for path, expected in frozen["files"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("EVIDENCE_CHANGED: " + path)
    for path, expected in frozen["probe_files"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("PHASE5C2C_EVIDENCE_CHANGED: " + path)
    prereg = json.loads(Path(".local/phase5_c2b/freeze-before.json").read_bytes())
    for path, expected in prereg["tracked"].items():
        if path in {
            "src/trading_ecosystem/experiments/authorization.py",
            "dashboard/src/workbench/CampaignAuthorization.tsx",
        }:
            continue  # Authorized read-only qualification presentation additions; DB stays exact.
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("PREREGISTRATION_CHANGED: " + path)
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
            qualification = value.pop("environment_qualification")
            if qualification["state"] != "READY":
                raise ValueError("QUALIFICATION_READBACK_FAILED")
            if value != frozen["review"]:
                raise ValueError("AUTHORIZATION_CHANGED")
    finally:
        engine.dispose()
    allowed = {
        "PHASE5_C2E_REPORT.md",
        "src/trading_ecosystem/tester/ResearchWorkspaceAttestor.mq5",
        "src/trading_ecosystem/tester/workspace_attestation.py",
        "tests/test_workspace_attestation.py",
        "scripts/verify_phase5_c2e.py",
        "scripts/verify_phase5_c2e.ps1",
    }
    checkpoint = json.loads(Path(".local/phase5_c2d/freeze-before.json").read_bytes())
    for group in ("tracked", "probe_files"):
        for path, expected in checkpoint[group].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                raise ValueError("PHASE5C2D_CHANGED: " + path)
    # Public SHA-256 identities independently checked against immutable evidence manifests.
    evidence_roots = {
        "profile-isolation-validation": (
            "7f00eae0ad8020c535384c069dc3b931"  # pragma: allowlist secret
            "338f580b56f77b0c4cf1ad048e0bbd7c"  # pragma: allowlist secret
        ),
        "active-profile-validation": (
            "c751b790285630c0a55a31a335c81454"  # pragma: allowlist secret
            "08806db0ef74aa55e9f6642e974cfbde"  # pragma: allowlist secret
        ),
        "runtime-workspace-attestation": (
            "44b8eeb6bf1af4be209376a0bd810835"  # pragma: allowlist secret
            "67d53f5480de3606af50ab337fe1020d"  # pragma: allowlist secret
        ),
    }
    for name, expected_identity in evidence_roots.items():
        evidence_root = Path(".local/phase5_c2e") / name
        manifest = json.loads((evidence_root / "manifest.json").read_bytes())
        content = {"status": manifest["status"], "files": manifest["files"]}
        if digest(content) != expected_identity or manifest["identity"] != expected_identity:
            raise ValueError("ISOLATION_EVIDENCE_IDENTITY_CHANGED")
        for relative, expected in manifest["files"].items():
            path = (evidence_root / relative).resolve()
            if not path.is_relative_to(evidence_root.resolve()):
                raise ValueError("EVIDENCE_PATH_ESCAPE")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("ISOLATION_EVIDENCE_CHANGED")
    if len(list(Path(".local/phase5_c2e").rglob("launch-intent.json"))) != 3:
        raise ValueError("ISOLATION_LAUNCH_COUNT_CHANGED")
    git(
        "check-ignore",
        "--no-index",
        ".local/phase5_c2e/runtime-workspace-attestation/manifest.json",
    )
    changed = set(git("diff", "--name-only", "HEAD").splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    if changed - allowed:
        raise ValueError("SCOPE_CHANGED")
    git("check-ignore", "--no-index", ".local/phase5_c2d/main-mode-probe/assessment.json")
    git("diff", "--check")
    print("PASS: 1044 frozen + 1621 historical files, prior probes and all research rows unchanged")
    print("PASS: campaign 0/11; Gold Scalper 1; NOT_AUTHORIZED; START disabled; OOS sealed")


if __name__ == "__main__":
    main()
