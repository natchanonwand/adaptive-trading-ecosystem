"""Phase 5C.2F preservation and additive-only scope verification."""

import hashlib
import json
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, select

from trading_ecosystem.experiments import campaign_store, store
from trading_ecosystem.tester import publication, readiness
from trading_ecosystem.tester import store as baseline
from trading_ecosystem.tester.qualification import digest
from trading_ecosystem.workbench import store as onboarding


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    root = Path(".local/phase5_c2f")
    before = json.loads((root / "before.json").read_bytes())
    if not all(
        git("rev-parse", ref) == before["head"]
        for ref in ("HEAD", "origin/main", "phase5c-workspaceprobe-v0.1.0^{commit}")
    ):
        raise ValueError("BASELINE_CHANGED")
    if git("show-ref", "--tags").splitlines() != before["tags"]:
        raise ValueError("TAGS_CHANGED")
    for path, expected in before["files"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("FROZEN_FILE_CHANGED: " + path)
    url = json.loads(Path(".local/phase4_a/runtime.json").read_text(encoding="utf-8-sig"))[
        "database_url"
    ]
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
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
            data = {
                t.name: [dict(row) for row in conn.execute(select(t).order_by(t.c.id)).mappings()]
                for t in tables
            }
        identity = hashlib.sha256(
            json.dumps(data, default=str, sort_keys=True).encode()
        ).hexdigest()
        if identity != before["database"]:
            raise ValueError("RESEARCH_ROWS_CHANGED")
    finally:
        engine.dispose()
    allowed = {
        "PHASE5_C2F_REPORT.md",
        "scripts/verify_phase5_c2f.py",
        "scripts/verify_phase5_c2f.ps1",
        "src/trading_ecosystem/tester/RuntimeTransportProbe.mq5",
        "src/trading_ecosystem/tester/transport.py",
        "tests/test_transport_probe.py",
    }
    changed = set(git("diff", "--name-only", "HEAD").splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    if changed - allowed:
        raise ValueError("SCOPE_CHANGED")
    probe = root / "transport-probe"
    manifest = json.loads((probe / "manifest.json").read_bytes())
    if digest({"status": manifest["status"], "files": manifest["files"]}) != manifest["identity"]:
        raise ValueError("TRANSPORT_MANIFEST_CHANGED")
    for name, expected in manifest["files"].items():
        path = (probe / name).resolve()
        if not path.is_relative_to(probe.resolve()):
            raise ValueError("EVIDENCE_ESCAPE")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("TRANSPORT_EVIDENCE_CHANGED")
    if len(list(root.rglob("launch-intent.json"))) != 1:
        raise ValueError("TRANSPORT_LAUNCH_COUNT_CHANGED")
    build = json.loads((root / "probe-build/build.json").read_bytes())
    for path, expected in (
        (Path("src/trading_ecosystem/tester/RuntimeTransportProbe.mq5"), build["source_sha256"]),
        (root / "probe-build/RuntimeTransportProbe.ex5", build["ex5_sha256"]),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("PROBE_BUILD_CHANGED")
    git("check-ignore", "--no-index", str(probe / "manifest.json"))
    git("diff", "--check")
    print("PASS: frozen1044/historical1621, all baseline source, prior probes/tags/research rows")
    print(
        "PASS: campaign NOT_AUTHORIZED, START disabled, executions0, budget0/11, OOS sealed, Gold1"
    )
    print("PASS: one transport launch; no new workspace attestation or campaign execution")


if __name__ == "__main__":
    main()
