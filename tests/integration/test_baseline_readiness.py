"""PostgreSQL readiness workflow; all candidates and execution boundaries are synthetic."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select

from tests.integration.test_baseline import migration, ready  # noqa: F401
from trading_ecosystem.tester import readiness, store
from trading_ecosystem.tester.service import Service


def test_config_attestation_audit_and_execution_guards(database: Engine, tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    run = ready(database, root, "UNKNOWN", "UNKNOWN")
    project_id = run.config.project_id
    with database.begin() as conn:
        events = readiness.history(conn, project_id)
        value = readiness.Authorization(
            event_id=uuid4(),
            previous_event_id=events[-1]["event_id"],
            provenance="UNKNOWN",
            source_reference="UNKNOWN",
            source_label="UNKNOWN",
            authorization_basis="UNKNOWN",
            confirmed=True,
        )
        unknown = readiness.attest(conn, project_id, value)
        assert readiness.attest(conn, project_id, value) == unknown
        view = readiness.detail(conn, root, project_id)
        assert view["verification"]["ea"] == "VERIFIED"
        assert "BLOCKED_AUTHORIZATION_PROVENANCE" in view["acceptance_readiness"]["reasons"]
        with pytest.raises(ValueError, match="BLOCKED_AUTHORIZATION_PROVENANCE"):
            store.create(conn, run.config.model_copy(update={"baseline_run_id": uuid4()}))
        before = conn.scalar(select(func.count()).select_from(store.runs))
        spec = readiness.BaselineConfiguration(
            configuration_id=uuid4(),
            project_id=project_id,
            parameters=run.config.model_dump(
                exclude={"baseline_run_id", "project_id", "configuration_id"}
            ),
            confirmed=True,
        )
        record = readiness.save_configuration(conn, root, spec)
        assert readiness.get_configuration(conn, spec.configuration_id) == record
        assert readiness.save_configuration(conn, root, spec) == record
        assert conn.scalar(select(func.count()).select_from(store.runs)) == before
        assert not record["exact_inputs_known"]
        assert record["specification"]["parameters"]["symbol"] == "XAUUSDm"
        assert (
            record["specification"]["parameters"]["tester_model"]
            == "EVERY_TICK_BASED_ON_REAL_TICKS"
        )
        with pytest.raises(ValueError, match="BLOCKED_SYMBOL"):
            readiness.save_configuration(
                conn,
                root,
                spec.model_copy(update={"parameters": {**spec.parameters, "symbol": "BTCUSDm"}}),
            )
        with pytest.raises(ValueError, match="IMMUTABLE"):
            readiness.save_configuration(
                conn,
                root,
                spec.model_copy(update={"parameters": {**spec.parameters, "leverage": 200}}),
            )
        authorized = value.model_copy(
            update={
                "event_id": uuid4(),
                "previous_event_id": unknown.event_id,
                "provenance": "USER_SUPPLIED_AUTHORIZED",
                "source_reference": "Synthetic fixture source",
                "source_label": "Test",
                "authorization_basis": "Authored test fixture",
            }
        )
        readiness.attest(conn, project_id, authorized)
        view = readiness.detail(conn, root, project_id)
        assert view["acceptance_readiness"] == {"status": "READY", "reasons": []}
        assert view["candidate"]["license_status"] == "UNKNOWN"
        assert view["candidate"]["tester_access_status"] == "UNKNOWN"
        assert len(view["authorization_history"]) == 3
        with pytest.raises(ValueError, match="STALE"):
            readiness.attest(conn, project_id, value.model_copy(update={"event_id": uuid4()}))
        prohibited = authorized.model_copy(
            update={
                "event_id": uuid4(),
                "previous_event_id": authorized.event_id,
                "provenance": "PROHIBITED_OR_UNVERIFIED",
            }
        )
        readiness.attest(conn, project_id, prohibited)
    service = Service(database, root, tmp_path / "evidence")
    with pytest.raises(ValueError, match="BLOCKED_AUTHORIZATION_PROVENANCE"):
        service.start(run.config.baseline_run_id)
    assert service.thread is None
    with database.connect() as conn:
        assert store.get(conn, run.config.baseline_run_id).status == "READY"


def test_http_configuration_save_is_not_execution(database: Engine, tmp_path: Path) -> None:
    import json
    from http.client import HTTPConnection

    from tests.integration.test_baseline import server

    run = ready(database, tmp_path, "UNKNOWN", "UNKNOWN")
    spec = readiness.BaselineConfiguration(
        configuration_id=uuid4(),
        project_id=run.config.project_id,
        parameters=run.config.model_dump(
            exclude={"baseline_run_id", "project_id", "configuration_id"}
        ),
        confirmed=True,
    )
    headers = {"Content-Type": "application/json", "X-Workbench-Request": "1"}
    with database.connect() as conn:
        count = conn.scalar(select(func.count()).select_from(store.runs))
    with server(database, tmp_path) as instance:
        connection = HTTPConnection("127.0.0.1", instance.server_port, timeout=10)
        path = "/workbench-api/baseline-configurations"
        connection.request(
            "POST", path, spec.model_dump_json(), {**headers, "Origin": "https://external.invalid"}
        )
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.request("POST", path, spec.model_dump_json(), headers)
        response = connection.getresponse()
        assert response.status == 201
        saved = json.loads(response.read())
        connection.request("GET", path + "/" + str(spec.configuration_id))
        response = connection.getresponse()
        assert response.status == 200 and json.loads(response.read()) == saved
        assert instance.service.thread is None
        connection.close()
    with database.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(store.runs)) == count
