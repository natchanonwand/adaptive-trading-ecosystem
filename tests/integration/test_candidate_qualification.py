"""Read-only qualification against PostgreSQL; synthetic binaries never execute."""

import hashlib
import json
from http.client import HTTPConnection
from os.path import relpath
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine, select

from tests.integration.test_baseline import (
    migration,  # noqa: F401
    server,
)
from tests.phase5b_helpers import EA, config
from tests.test_phase5b_environment import binding
from tests.test_phase5b_installed_profile import complete_proof
from tests.test_phase5b_qualification import proof
from trading_ecosystem.tester import process, qualification, readiness, store
from trading_ecosystem.workbench import store as onboarding
from trading_ecosystem.workbench.contracts import Binding, CandidateInput, CreateProject


@pytest.mark.parametrize("installed_mode", [False, True])
@pytest.mark.parametrize(
    "case,expected",
    [
        ("market", "BLOCKED_CANDIDATE_INGESTION_MODEL"),
        ("upload", "BLOCKED_CANDIDATE_INGESTION_MODEL"),
        ("unsupported", "BLOCKED_CANDIDATE_INGESTION_MODEL"),
        ("absent_authorization", "BLOCKED_AUTHORIZATION_PROVENANCE"),
        ("mismatch", "BLOCKED_ARTIFACT_IDENTITY_MISMATCH"),
        ("installed_mismatch", "BLOCKED_ARTIFACT_IDENTITY_MISMATCH"),
        ("installed_missing", "BLOCKED_CANDIDATE_INGESTION_MODEL"),
        ("wrong_candidate", "BASELINE_CONFIGURATION_ARTIFACT_MISMATCH"),
        ("missing_configuration", "BASELINE_CONFIGURATION_REQUIRED"),
        ("wrong_terminal", "BLOCKED_TERMINAL_IDENTITY_MISMATCH"),
        ("license", "BLOCKED_LICENSE"),
        ("tester", "BLOCKED_TESTER_ACCESS"),
    ],
)
def test_qualification_preserves_every_persisted_record(
    database: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected: str,
    installed_mode: bool,
) -> None:
    artifacts = tmp_path / "artifacts"
    terminal = binding(tmp_path)
    evidence = (complete_proof if installed_mode else proof)(tmp_path / "proof", terminal)
    if installed_mode and case == "market":
        expected = "CANDIDATE_EXECUTION_READY"
    if installed_mode and case == "installed_missing":
        expected = "BLOCKED_CANDIDATE_PROFILE_MISMATCH"
    output = Path(
        ".local/phase5_b1g/synthetic" if installed_mode else ".local/phase5_b1f/synthetic"
    ).resolve()
    with database.begin() as conn:
        artifact = onboarding.register_artifact(conn, artifacts, "synthetic.ex5", "EA", EA)
        p = onboarding.create_project(
            conn,
            artifacts,
            CreateProject(
                project_id=uuid4(),
                project_name="Synthetic qualification",
                source_type="EXTERNAL_EA",
                candidate=CandidateInput(artifact_id=artifact.artifact_id),
                broker_binding=Binding(
                    broker_name="Synthetic demo",
                    canonical_asset="XAUUSD",
                    broker_symbol="XAUUSDm",
                    timeframe="M5",
                    symbol_confirmed=True,
                ),
            ),
        )
        cfg = config(project_id=p.project_id, timeframe="M5")
        configuration_id = uuid4()
        readiness.save_configuration(
            conn,
            artifacts,
            readiness.BaselineConfiguration(
                configuration_id=configuration_id,
                project_id=p.project_id,
                parameters=cfg.model_dump(
                    mode="json", exclude={"baseline_run_id", "project_id", "configuration_id"}
                ),
                confirmed=True,
            ),
        )
        if case != "absent_authorization":
            readiness.attest(
                conn,
                p.project_id,
                readiness.Authorization(
                    event_id=uuid4(),
                    provenance=(
                        "USER_SUPPLIED_AUTHORIZED"
                        if case == "upload"
                        else "FREE_VENDOR_DISTRIBUTION"
                        if case == "unsupported"
                        else "MARKETPLACE_AUTHORIZED"
                    ),
                    source_reference="synthetic source",
                    source_label="synthetic source",
                    authorization_basis="Synthetic fixture authored for this test",
                    confirmed=True,
                ),
            )
        if case in {"license", "tester"}:
            c = onboarding.get_candidate(conn, p.candidate_id)
            body = c.model_dump(mode="json")
            body["license_status" if case == "license" else "tester_access_status"] = (
                "NOT_AUTHORIZED" if case == "license" else "UNAVAILABLE"
            )
            conn.execute(
                onboarding.candidates.update()
                .where(onboarding.candidates.c.id == str(p.candidate_id))
                .values(body=body)
            )
    market = terminal.terminal_data_root / "MQL5/Experts/Market"
    market.mkdir(parents=True)
    installed = market / artifact.filename
    if case != "installed_missing":
        installed.write_bytes(b"changed" if case == "installed_mismatch" else EA)
    if case == "mismatch":
        onboarding.artifact_path(artifacts, artifact).write_bytes(b"changed")
    if case == "wrong_terminal":
        terminal = terminal.model_copy(update={"terminal_binding_id": uuid4()})

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Qualification must not execute or copy")

    import shutil

    monkeypatch.setattr(shutil, "copyfile", forbidden)
    monkeypatch.setattr(process, "execute", forbidden)
    before_files = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    tables = [
        onboarding.projects,
        onboarding.candidates,
        onboarding.artifacts,
        readiness.authorizations,
        readiness.configurations,
        store.runs,
        store.results,
    ]
    with database.connect() as conn:
        before = {t.name: list(conn.execute(select(t).order_by(t.c.id)).mappings()) for t in tables}
        result = qualification.qualify(
            conn,
            artifacts,
            p.project_id,
            uuid4() if case == "wrong_candidate" else p.candidate_id,
            uuid4() if case == "missing_configuration" else configuration_id,
            terminal,
            evidence,
            output,
            installed_profile=installed_mode,
        )
        assert result["status"] == expected
        after = {t.name: list(conn.execute(select(t).order_by(t.c.id)).mappings()) for t in tables}
        assert before == after
        if case in {"market", "upload"}:
            assert result["artifact"] == "VERIFIED"
            assert result["authorization"] == "VERIFIED_USER_ATTESTATION"
            assert result["declared_license_status"] == "UNKNOWN"
            assert result["declared_tester_access_status"] == "UNKNOWN"
            assert result["observed_tester_access_status"] == "UNKNOWN"
            proposed = result["execution_binding"]
            again = qualification.qualify(
                conn,
                artifacts,
                p.project_id,
                p.candidate_id,
                configuration_id,
                terminal,
                evidence,
                output,
                qualification_id=__import__("uuid").UUID(proposed["content"]["qualification_id"]),
                installed_profile=installed_mode,
            )
            qualification.verify_binding(proposed, again["execution_binding"])
            assert "Login=" not in result["native_config"]
    assert result["candidate_native_attempts"] == 0 and not result["execution_available"]
    assert result["actual_execution_result"] == "NOT_EXECUTED"
    assert before_files == {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }


def test_candidate_readiness_http_is_read_only_and_sanitized(
    database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    terminal = binding(tmp_path)
    project_id, candidate_id, config_id = uuid4(), uuid4(), uuid4()
    calls: list[dict[str, Any]] = []

    def dry_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        assert args[2:5] == (project_id, candidate_id, config_id)
        assert args[5] == terminal and kwargs == {"installed_profile": True}
        assert args[6].is_absolute() and args[7].is_absolute()
        calls.append(kwargs)
        return {
            "configuration_id": str(config_id),
            "status": "CANDIDATE_EXECUTION_READY",
            "authorization": "VERIFIED_USER_ATTESTATION",
            "artifact": "VERIFIED",
            "native_config_dry_run": "VERIFIED_DRY_RUN_NO_LAUNCH",
            "declared_license_status": "UNKNOWN",
            "declared_tester_access_status": "UNKNOWN",
            "observed_tester_access_status": "UNKNOWN",
            "expert_path": "PRIVATE_NATIVE_PATH",
        }

    monkeypatch.setattr(qualification, "qualify", dry_run)
    monkeypatch.setattr(store, "project", lambda *_: SimpleNamespace(candidate_id=candidate_id))
    with server(database, tmp_path) as instance:
        (instance.service.root / "terminal-binding.json").write_text(terminal.model_dump_json())
        # Production starts with a relative .local root; preserve that boundary in this test.
        instance.service.root = Path(relpath(instance.service.root))
        before = {}
        tables = [store.runs, store.results, readiness.configurations]
        with database.connect() as conn:
            before = {t.name: list(conn.execute(select(t)).mappings()) for t in tables}
        connection = HTTPConnection("127.0.0.1", instance.server_port, timeout=10)
        route = (
            f"/workbench-api/baseline-candidate-readiness?project_id={project_id}"
            f"&configuration_id={config_id}"
        )
        connection.request("GET", route)
        response = connection.getresponse()
        body = response.read().decode()
        assert response.status == 200 and "PRIVATE_NATIVE_PATH" not in body
        assert json.loads(body)["execution_available"] is False
        connection.request("GET", route + f"&configuration_id={config_id}")
        response = connection.getresponse()
        assert response.status == 400
        response.read()
        connection.request("GET", route, headers={"Origin": "https://outside.invalid"})
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.close()
        assert len(calls) == 1
        with database.connect() as conn:
            assert before == {t.name: list(conn.execute(select(t)).mappings()) for t in tables}
