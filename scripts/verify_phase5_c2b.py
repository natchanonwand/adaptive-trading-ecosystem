"""Strict prior-row/evidence preservation plus exactly one nonexecuted reference plan."""

import hashlib
import json
import subprocess
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select

from trading_ecosystem.experiments import campaign_store, store
from trading_ecosystem.experiments.authorization import review
from trading_ecosystem.experiments.campaigns import generate
from trading_ecosystem.experiments.reference_contract import parse_definition
from trading_ecosystem.tester import publication, readiness
from trading_ecosystem.tester import store as baseline
from trading_ecosystem.workbench import store as onboarding

BASE = "1c304eff4e17b26d5ea4121147aa3ec03c1bb9c0"  # pragma: allowlist secret


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    allowed = {
        "PHASE5_C2B_REPORT.md",
        "dashboard/src/workbench/CampaignPanel.tsx",
        "dashboard/src/workbench/CampaignAuthorization.tsx",
        "dashboard/tests/campaign-authorization.test.tsx",
        "scripts/prepare_phase5_c2b.py",
        "scripts/verify_phase5_c2b.py",
        "scripts/verify_phase5_c2b.ps1",
        "src/trading_ecosystem/experiments/api.py",
        "src/trading_ecosystem/experiments/store.py",
        "src/trading_ecosystem/experiments/campaigns.py",
        "src/trading_ecosystem/experiments/campaign_api.py",
        "src/trading_ecosystem/experiments/campaign_runner.py",
        "src/trading_ecosystem/experiments/campaign_store.py",
        "src/trading_ecosystem/experiments/baseline_boundary.py",
        "src/trading_ecosystem/experiments/authorization.py",
        "src/trading_ecosystem/experiments/reference_contract.py",
        "src/trading_ecosystem/experiments/reference_preparation.py",
        "src/trading_ecosystem/experiments/ReferenceEmaCrossM5.mq5",
        "src/trading_ecosystem/tester/readiness.py",
        "src/trading_ecosystem/tester/qualification.py",
        "src/trading_ecosystem/workbench/store.py",
        "src/trading_ecosystem/workbench/contracts.py",
        "tests/test_reference_campaign.py",
        "tests/integration/test_reference_campaign.py",
    }
    changed = set(git("diff", "--name-only", "HEAD").splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    if changed - allowed:
        raise ValueError("OUTSIDE_PHASE5C2B_SCOPE: " + repr(sorted(changed - allowed)))
    for ref in ("HEAD", "origin/main", "ui-retro-v0.3.0^{commit}"):
        if git("rev-parse", ref) != BASE:
            raise ValueError("FROZEN_UI_BASELINE_CHANGED")
    tags = set(json.loads(Path(".local/ui2/tags-before.json").read_text(encoding="utf-8-sig")))
    tags.add("c54b67d8ee0fc05948fe755748afab0d4a0d6134 refs/tags/ui-retro-v0.3.0")
    if tags != set(git("show-ref", "--tags").splitlines()):
        raise ValueError("PRIOR_TAG_CHANGED")
    for path, count in [
        (".local/phase4_e/preserved-evidence.json", 1044),
        (".local/phase5_c0/preserved-before.json", 1621),
    ]:
        rows = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if len(rows) != count:
            raise ValueError("EVIDENCE_INVENTORY_CHANGED")
        for name, sha in rows.items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != sha.lower():
                raise ValueError("FROZEN_EVIDENCE_CHANGED: " + name)
        print(f"PASS: {count} evidence files byte-identical")
    registration = json.loads(Path(".local/phase5_c2b/registration.json").read_bytes())
    before = json.loads(Path(".local/phase5_c0/database-before.json").read_bytes())
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
            ]
            for table in tables:
                rows = list(conn.execute(select(table).order_by(table.c.id)).mappings())
                prior = {r["id"]: r for r in before[table.name]}
                current = {r["id"]: dict(r) for r in rows}
                if any(current.get(k) != v for k, v in prior.items()):
                    raise ValueError("HISTORICAL_ROW_CHANGED")
                expected_new = (
                    0 if table in (baseline.runs, baseline.results, publication.publications) else 1
                )
                if len(current) - len(prior) != expected_new:
                    raise ValueError("UNEXPECTED_NEW_ROWS")
            campaigns = list(conn.execute(select(campaign_store.records.c.id)).scalars())
            if campaigns != [registration["campaign"]["id"]]:
                raise ValueError("UNEXPECTED_CAMPAIGN")
            body = campaign_store.read(conn, UUID(campaigns[0]))
            if body["runs"] or body["consumed_executions"] or body["started_at"] is not None:
                raise ValueError("UNAUTHORIZED_EXECUTION")
            d = parse_definition(body["definition"])
            if body["plan"]["candidates"] != generate(d) or len(generate(d)) != 9:
                raise ValueError("CANDIDATE_PLAN_CHANGED")
            if body != registration["campaign"]:
                raise ValueError("PREREGISTRATION_CHANGED")
            definitions = list(conn.execute(select(store.records.c.id)).scalars())
            if definitions != [body["definition_id"]]:
                raise ValueError("UNEXPECTED_DEFINITION")
            checked = review(
                conn,
                UUID(body["id"]),
                Path(".local/artifacts/research_projects"),
                Path(".local/phase5_b"),
            )
            if checked.get("review_identity") != registration["authorization_review"].get(
                "review_identity"
            ):
                raise ValueError("AUTHORIZATION_BINDINGS_CHANGED")
    finally:
        engine.dispose()
    git(
        "check-ignore",
        "--no-index",
        ".local/phase5_c2b/build1/ReferenceEmaCrossM5.ex5",
        "dashboard/dist",
    )
    git("diff", "--check")
    print("PASS: prior Phase 5B rows unchanged; one reference plan; zero campaign executions")


if __name__ == "__main__":
    main()
