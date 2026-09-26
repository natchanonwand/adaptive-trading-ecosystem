"""Workbench persistence, migration and HTTP boundaries on fresh PostgreSQL."""

import base64
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import closing
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from trading_ecosystem.workbench import store
from trading_ecosystem.workbench.api import WorkbenchServer
from trading_ecosystem.workbench.contracts import (
    Binding,
    CandidateInput,
    CreateProject,
    SourceType,
    Status,
    transition,
)


@pytest.fixture(scope="module", autouse=True)
def migration(database: Engine) -> None:
    environment = dict(os.environ)
    environment["TE_DATABASE_URL"] = database.url.render_as_string(hide_password=False)
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic-workbench.ini", "upgrade", "head"],
            env=environment,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, "Workbench migration failed (driver details suppressed)"
    with database.connect() as conn:
        assert (
            conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
            == "0001_journal"
        )
        assert (
            conn.execute(text("SELECT version_num FROM workbench.alembic_version")).scalar_one()
            == "0001_projects"
        )


def request(**changes: Any) -> CreateProject:
    values: dict[str, Any] = dict(
        project_id=uuid4(),
        project_name="Synthetic onboarding test",
        source_type=SourceType.EXTERNAL_EA,
        candidate=CandidateInput(),
        broker_binding=Binding(),
    )
    values.update(changes)
    return CreateProject.model_validate(values)


def test_project_identity_and_unknowns(database: Engine, tmp_path: Path) -> None:
    req = request()
    with database.begin() as conn:
        project = store.create_project(conn, tmp_path, req)
        assert store.create_project(conn, tmp_path, req) == project
        assert project.status == Status.DRAFT
        detail = store.detail(conn, tmp_path, project.project_id)
        assert detail["candidate"]["vendor"] == "UNKNOWN"
        assert detail["verification"] == {"ea": "NOT_PROVIDED", "manual": "NOT_PROVIDED"}
        assert detail["execution_available"] is False
        assert any(
            p["project_id"] == str(project.project_id) for p in store.list_projects(conn)["items"]
        )
        with pytest.raises(ValueError, match="PROJECT_ID_CONFLICT"):
            store.create_project(conn, tmp_path, req.model_copy(update={"project_name": "Changed"}))


def test_artifact_identity_manual_and_tampering(database: Engine, tmp_path: Path) -> None:
    data = b"synthetic opaque test bytes; not an executable EA"
    with database.begin() as conn:
        artifact = store.register_artifact(conn, tmp_path, "fixture.ex5", "EA", data)
        duplicate = store.register_artifact(conn, tmp_path, "renamed.ex5", "EA", data)
        assert duplicate == artifact
        assert artifact.sha256 == hashlib.sha256(data).hexdigest()
        manual = store.register_artifact(conn, tmp_path, "fixture.pdf", "MANUAL", b"opaque manual")
        candidate = CandidateInput(
            artifact_id=artifact.artifact_id,
            manual_id=manual.artifact_id,
            license_status="USER_ATTESTED",
            tester_access_status="USER_CONFIRMED",
        )
        binding = Binding(
            broker_name="Synthetic demo",
            canonical_asset="XAUUSD",
            broker_symbol="XAUUSDm",
            timeframe="H1",
            symbol_confirmed=True,
        )
        project = store.create_project(
            conn, tmp_path, request(candidate=candidate, broker_binding=binding)
        )
        assert project.status == Status.BASELINE_READY
        assert store.detail(conn, tmp_path, project.project_id)["baseline_status"] == "READY"
        store.artifact_path(tmp_path, artifact).write_bytes(b"tampered")
        detail = store.detail(conn, tmp_path, project.project_id)
        assert detail["baseline_status"] == "NOT_READY"
        assert detail["verification"]["ea"] == "FAILED"
        with pytest.raises(ValueError, match="INTEGRITY"):
            store.create_project(
                conn, tmp_path, request(candidate=candidate, broker_binding=binding)
            )
        with pytest.raises(ValueError, match="INTEGRITY"):
            store.register_artifact(conn, tmp_path, "fixture.ex5", "EA", data)


@pytest.mark.parametrize(
    "filename,role,data",
    [
        ("../escape.ex5", "EA", b"x"),
        ("C:\\file.ex5", "EA", b"x"),
        ("file.exe", "EA", b"x"),
        ("file.ex5", "EA", b""),
        ("file.pdf", "EA", b"x"),
        ("file.ex5", "OTHER", b"x"),
        ("file.ex5", "EA", b"x" * (store.MAX_BYTES + 1)),
    ],
    ids=["traversal", "absolute", "extension", "empty", "role-extension", "role", "oversize"],
)
def test_invalid_artifacts(
    database: Engine, tmp_path: Path, filename: str, role: str, data: bytes
) -> None:
    with database.begin() as conn, pytest.raises(ValueError, match="INVALID_ARTIFACT"):
        store.register_artifact(conn, tmp_path, filename, role, data)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "source", [SourceType.STRATEGY_IDEA, SourceType.QUANT_FORMULA, SourceType.MANUAL_TRADING]
)
def test_future_sources_rejected(database: Engine, tmp_path: Path, source: SourceType) -> None:
    with database.begin() as conn, pytest.raises(ValueError, match="COMING_SOON"):
        store.create_project(conn, tmp_path, request(source_type=source))


@pytest.mark.parametrize(
    "changes",
    [
        {"project_name": " "},
        {"source_type": ""},
        {"broker_binding": {"environment": "LIVE"}},
        # Synthetic field tests strict rejection of credential input.
        {"candidate": {"password": "not accepted"}},  # pragma: allowlist secret
        {"candidate": {"notes": "password=synthetic"}},
        {"candidate": {"known_magic_number": 2**53}},
    ],
)
def test_invalid_contract(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        request(**changes)


def test_source_required() -> None:
    body = request().model_dump()
    del body["source_type"]
    with pytest.raises(ValueError):
        CreateProject.model_validate(body)


@pytest.mark.parametrize(
    "license_status,bound,tester,status",
    [
        ("UNKNOWN", False, "UNKNOWN", Status.BLOCKED_LICENSE),
        ("USER_ATTESTED", False, "USER_CONFIRMED", Status.BLOCKED_SYMBOL),
        ("USER_ATTESTED", True, "UNKNOWN", Status.BLOCKED_TESTER),
        ("USER_ATTESTED", True, "USER_CONFIRMED", Status.BASELINE_READY),
    ],
)
def test_persisted_readiness_without_manual(
    database: Engine, tmp_path: Path, license_status: str, bound: bool, tester: str, status: Status
) -> None:
    with database.begin() as conn:
        artifact = store.register_artifact(
            conn, tmp_path, "readiness.ex5", "EA", b"readiness fixture"
        )
        candidate = CandidateInput.model_validate(
            dict(
                artifact_id=artifact.artifact_id,
                license_status=license_status,
                tester_access_status=tester,
            )
        )
        binding = Binding(
            broker_name="demo",
            canonical_asset="BTCUSD",
            broker_symbol="BTCUSDm",
            timeframe="M5",
            symbol_confirmed=bound,
        )
        project = store.create_project(
            conn, tmp_path, request(candidate=candidate, broker_binding=binding)
        )
        assert project.status == status
        assert store.detail(conn, tmp_path, project.project_id)["project"]["status"] == status.value


def test_invalid_artifact_reference_leaves_no_partial_records(
    database: Engine, tmp_path: Path
) -> None:
    req = request(candidate=CandidateInput(artifact_id=uuid4()))
    with database.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM workbench.candidates")).scalar_one()
    with pytest.raises(ValueError, match="ARTIFACT_NOT_FOUND"), database.begin() as conn:
        store.create_project(conn, tmp_path, req)
    with database.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM workbench.candidates")).scalar_one() == before
        )
        with pytest.raises(ValueError, match="PROJECT_NOT_FOUND"):
            store.detail(conn, tmp_path, req.project_id)


@pytest.mark.parametrize(
    "asset,symbol",
    [("BTCUSD", "BTCUSDm"), ("XAUUSD", "XAUUSDm"), ("USTEC100", "USTECm"), ("US100", "USTECm")],
)
def test_explicit_mapping(asset: str, symbol: str) -> None:
    values = dict(broker_name="demo", canonical_asset=asset, broker_symbol=symbol, timeframe="H1")
    assert not Binding.model_validate(values).ready()
    assert Binding.model_validate({**values, "symbol_confirmed": True}).ready()
    assert not Binding.model_validate(
        {**values, "symbol_confirmed": True, "broker_symbol": "UNKNOWN"}
    ).ready()


def test_transition_boundary() -> None:
    assert transition(Status.DRAFT, Status.CANDIDATE_REGISTERED) == Status.CANDIDATE_REGISTERED
    assert transition(Status.CANDIDATE_REGISTERED, Status.BLOCKED_LICENSE) == Status.BLOCKED_LICENSE
    for future in (
        Status.BASELINE_RUNNING,
        Status.BASELINE_COMPLETE,
        Status.TUNING_READY,
        Status.BEHAVIOR_READY,
        Status.FORWARD_READY,
    ):
        with pytest.raises(ValueError):
            transition(Status.BASELINE_READY, future)


@pytest.fixture
def server(database: Engine, tmp_path: Path) -> Iterator[WorkbenchServer]:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "workbench.html").write_text("<html>Workbench</html>")
    with WorkbenchServer(database, tmp_path / "artifacts", frontend, port=0) as instance:
        thread = Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        try:
            yield instance
        finally:
            instance.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


def http(
    server: WorkbenchServer, path: str, body: Any = None, headers: dict[str, str] | None = None
) -> tuple[int, Any]:
    with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as conn:
        conn.request(
            "GET" if body is None else "POST",
            path,
            body=None if body is None else json.dumps(body),
            headers=headers
            if headers is not None
            else {"Content-Type": "application/json", "X-Workbench-Request": "1"},
        )
        response = conn.getresponse()
        return response.status, json.loads(response.read())


def test_http_onboarding(server: WorkbenchServer) -> None:
    code, catalog = http(server, "/workbench-api/catalog")
    assert code == 200 and len(catalog["items"]) == 3 and catalog["endorsement"] is False
    assert all(c["source_reference"] == "UNKNOWN" for c in catalog["items"])
    code, artifact = http(
        server,
        "/workbench-api/artifacts",
        {
            "filename": "http-fixture.ex5",
            "role": "EA",
            "data_base64": base64.b64encode(b"synthetic HTTP fixture").decode(),
        },
    )
    assert code == 201
    req = request(candidate=CandidateInput(artifact_id=artifact["artifact_id"]))
    code, project = http(server, "/workbench-api/projects", req.model_dump(mode="json"))
    assert code == 201 and project["status"] == "BLOCKED_LICENSE"
    assert http(server, "/workbench-api/projects/" + project["project_id"])[0] == 200
    assert http(server, "/workbench-api/candidates/" + project["candidate_id"])[0] == 200
    assert http(server, "/workbench-api/projects")[0] == 200


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Host": "attacker.invalid"},
        {"Origin": "https://attacker.invalid", "X-Workbench-Request": "1"},
        {"Sec-Fetch-Site": "cross-site", "X-Workbench-Request": "1"},
    ],
)
def test_http_write_origin_boundary(server: WorkbenchServer, headers: dict[str, str]) -> None:
    assert http(server, "/workbench-api/projects", {}, headers)[0] == 403


@pytest.mark.parametrize(
    "path",
    [
        "/.env",
        "/artifacts/file.ex5",
        "/assets/../../.env",
        "/workbench-api/projects?offset=-1",
        "/workbench-api/projects?offset=0&offset=1",
    ],
)
def test_http_no_file_or_secret_exposure(server: WorkbenchServer, path: str) -> None:
    code, body = http(server, path)
    assert code in {400, 404}
    assert "postgresql" not in json.dumps(body)


def test_http_no_execution_or_credential_storage(server: WorkbenchServer) -> None:
    assert http(server, "/workbench-api/run-baseline", {})[0] == 404
    body = request().model_dump(mode="json")
    # Synthetic input exercises rejection, never a real credential.
    body["broker_binding"]["password"] = "synthetic-not-a-secret"  # pragma: allowlist secret
    code, result = http(server, "/workbench-api/projects", body)
    assert code == 400 and "synthetic" not in json.dumps(result)
