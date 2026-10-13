"""One-time authorized reference registration. No native execution or authorization grant."""

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import create_engine

from trading_ecosystem.experiments import campaign_store, store
from trading_ecosystem.experiments.authorization import review
from trading_ecosystem.experiments.contracts import digest
from trading_ecosystem.experiments.reference_preparation import definition
from trading_ecosystem.tester import readiness
from trading_ecosystem.workbench import store as onboarding
from trading_ecosystem.workbench.contracts import CreateProject

QUALIFIED_REPORT_SHA = (
    "eb855831763c4b45a5463518b2e22f743146a9808b9b6ff4d67178c56516bc42"  # pragma: allowlist secret
)


def main() -> None:
    root = Path(".local/phase5_c2b")
    receipt = root / "registration.json"
    if receipt.exists():
        raise ValueError("REGISTRATION_EXISTS_USE_READBACK_NOT_RECREATE")
    source = Path("src/trading_ecosystem/experiments/ReferenceEmaCrossM5.mq5")
    builds = [
        json.loads((root / name / "receipt.json").read_bytes()) for name in ("build1", "build2")
    ]
    same = json.loads((root / "reproducibility.json").read_bytes())
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    assert all(b["source_sha256"] == source_sha for b in builds + same)
    assert all(b["valid"] and "Result: 0 errors, 0 warnings" in b["diagnostics"] for b in builds)
    assert builds[0]["compiler_sha256"] == builds[1]["compiler_sha256"]
    assert builds[0]["compiler_identity"]["build"] == "6230"
    artifact = root / "build1/ReferenceEmaCrossM5.ex5"
    binary = artifact.read_bytes()
    assert hashlib.sha256(binary).hexdigest() == builds[0]["ex5_sha256"]
    content = {
        "source_sha256": source_sha,
        "canonical_ex5_sha256": builds[0]["ex5_sha256"],
        "compiler_identity": builds[0]["compiler_identity"],
        "compiler_sha256": builds[0]["compiler_sha256"],
        "diagnostics_sha256": hashlib.sha256(
            (root / "build1/ReferenceEmaCrossM5.log").read_bytes()
        ).hexdigest(),
        "qualification_build_hashes": [b["ex5_sha256"] for b in builds + same],
        "selection": "FIRST_SUCCESSFUL_QUALIFICATION_BUILD_NO_PERFORMANCE_OBSERVATION",
        "source_reproducibility": "VERIFIED",
        "build_repeatability": "VERIFIED",
        "bit_reproducibility": "NOT_ESTABLISHED",
        "variation_cause": "COMPILER_OUTPUT_NONDETERMINISM_CAUSE_UNKNOWN",
        "rebuild_policy": "NEW_ARTIFACT_REQUIRES_EXPLICIT_REQUALIFICATION",
    }
    build: dict[str, Any] = {"content": content, "identity": digest(content)}
    build_path = root / "canonical-build.json"
    if build_path.exists():
        assert json.loads(build_path.read_bytes()) == build
    else:
        with build_path.open("x", encoding="utf-8") as output:
            json.dump(build, output, indent=2)
    url = json.loads(Path(".local/phase4_a/runtime.json").read_text(encoding="utf-8-sig"))[
        "database_url"
    ]
    engine = create_engine(url)
    artifacts = Path(".local/artifacts/research_projects")
    project_id = uuid5(NAMESPACE_URL, "phase5c2b-reference:" + build["identity"])
    config_id = uuid5(project_id, "baseline")
    try:
        with engine.begin() as conn:
            registered = onboarding.register_artifact(conn, artifacts, artifact.name, "EA", binary)
            project = onboarding.create_project(
                conn,
                artifacts,
                CreateProject.model_validate(
                    dict(
                        project_id=str(project_id),
                        project_name="Reference EMA M5 Pipeline Qualification",
                        source_type="PROJECT_OWNED_REFERENCE",
                        candidate=dict(
                            product_name="ReferenceEmaCrossM5",
                            version="1.00",
                            vendor="Project-owned",
                            artifact_id=str(registered.artifact_id),
                            license_status="USER_ATTESTED",
                            tester_access_status="USER_CONFIRMED",
                            source_reference="PROJECT_SOURCE SHA256:" + source_sha,
                            notes="REFERENCE ONLY; not a production strategy; canonical build "
                            + build["identity"],
                            known_magic_number=52020001,
                        ),
                        broker_binding=dict(
                            broker_name="Exness",
                            canonical_asset="XAUUSD",
                            broker_symbol="XAUUSDm",
                            timeframe="M5",
                            environment="DEMO",
                            symbol_confirmed=True,
                        ),
                    )
                ),
            )
            readiness.attest(
                conn,
                project_id,
                readiness.Authorization(
                    event_id=uuid5(project_id, "source-authorization"),
                    provenance="PROJECT_SOURCE",
                    source_reference=str(source),
                    source_label="PROJECT_OWNED_REFERENCE",
                    authorization_basis="Project source and canonical EX5; pipeline research only",
                    confirmed=True,
                ),
            )
            config = readiness.save_configuration(
                conn,
                artifacts,
                readiness.BaselineConfiguration(
                    configuration_id=config_id,
                    project_id=project_id,
                    confirmed=True,
                    parameters=dict(
                        symbol="XAUUSDm",
                        timeframe="M5",
                        tester_model="EVERY_TICK_BASED_ON_REAL_TICKS",
                        from_date="2026-01-01",
                        to_date="2026-06-30",
                        initial_deposit="300",
                        currency="USD",
                        leverage=100,
                        timeout_seconds=600,
                        environment="DEMO_RESEARCH_TESTER",
                        input_provenance="USER_CONFIRMED_VALUES",
                        input_reference="PROJECT_SOURCE SHA256:" + source_sha,
                        set_text="InpFastEmaPeriod=20\nInpSlowEmaPeriod=100",
                    ),
                ),
            )
            # Existing qualified raw report identifies observed history, not future availability.
            d = definition(
                str(project_id),
                str(project.candidate_id),
                str(config_id),
                config["configuration_identity"],
                build,
                QUALIFIED_REPORT_SHA,
            )
            saved = store.save(conn, d)
            store.freeze(conn, UUID(saved["id"]))
            campaign = campaign_store.create(conn, UUID(saved["id"]), d.identity)
            assessed = review(conn, UUID(campaign["id"]), artifacts, Path(".local/phase5_b"))
            result = {
                "project_id": str(project_id),
                "candidate_id": str(project.candidate_id),
                "configuration_id": str(config_id),
                "definition": d.model_dump(mode="json"),
                "definition_identity": d.identity,
                "campaign": campaign,
                "authorization_review": assessed,
                "build": build,
            }
        with receipt.open("x", encoding="utf-8") as output:
            json.dump(result, output, indent=2)
        print(
            json.dumps(
                {k: result[k] for k in ("project_id", "candidate_id", "definition_identity")},
                indent=2,
            )
        )
        print("PRE_REGISTERED; no authorization granted; no execution")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
