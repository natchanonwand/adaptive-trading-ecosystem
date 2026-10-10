"""Isolated PostgreSQL definition contracts; no real campaign or native execution."""

import json
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Engine, select

from tests.integration import test_installed_execution as isolated
from tests.integration.test_baseline import migration, ready  # noqa: F401
from tests.test_experiments import definition_data
from trading_ecosystem.experiments import store
from trading_ecosystem.experiments.api import ExperimentServer
from trading_ecosystem.experiments.contracts import ExperimentDefinition
from trading_ecosystem.tester import process, publication, readiness
from trading_ecosystem.tester import store as baseline
from trading_ecosystem.tester.service import Service

database = isolated.database


def fixture_definition(database: Engine, tmp_path: Path) -> ExperimentDefinition:
    run = ready(database, tmp_path / "artifacts")
    assert run.config.configuration_id is not None
    with database.connect() as conn:
        config = readiness.get_configuration(conn, run.config.configuration_id)
        project = baseline.project(conn, run.config.project_id)
    value = definition_data()
    value.update(
        project_id=str(run.config.project_id),
        candidate_id=str(run.candidate_id),
        baseline_configuration_id=str(run.config.configuration_id),
        baseline_identity=config["configuration_identity"],
        broker=project.broker_binding.broker_name,
    )
    return ExperimentDefinition.model_validate(value)


def snapshot(database: Engine) -> dict[str, Any]:
    tables = [
        baseline.runs,
        baseline.results,
        readiness.configurations,
        readiness.authorizations,
        publication.publications,
    ]
    with database.connect() as c:
        return {t.name: list(c.execute(select(t).order_by(t.c.id)).mappings()) for t in tables}


def test_append_only_definition_freeze_and_violations(
    database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = fixture_definition(database, tmp_path)
    before = snapshot(database)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("No native execution or new baseline run permitted")

    monkeypatch.setattr(process, "execute", forbidden)
    monkeypatch.setattr(Service, "start", forbidden)
    monkeypatch.setattr(baseline, "create", forbidden)
    with database.begin() as c:
        draft = store.save(c, d)
        assert store.save(c, d) == draft
        frozen = store.freeze(c, UUID(draft["id"]))
        assert frozen["state"] == "FROZEN" and frozen["definition"] == draft["definition"]
        assert store.save(c, d) == frozen
        assert store.freeze(c, UUID(draft["id"])) == frozen
        for action in ("run", "search", "unlock-oos", "relock-oos", "update"):
            assert (
                store.reject_action(c, UUID(draft["id"]), action)["event"] == "PROTOCOL_VIOLATION"
            )
        events = list(c.execute(select(store.violations.c.body)).scalars())
        assert sum(e["event"] == "PROTOCOL_VIOLATION" for e in events) == 5
        assert sum(e["event"] == "DEFINITION_FROZEN" for e in events) == 1
        assert all(e["recorded_at"] for e in events)
        changed = d.model_dump(mode="json")
        changed["budget"]["maximum_configurations"] = 2
        new = store.save(c, ExperimentDefinition.model_validate(changed))
        assert new["identity"] != frozen["identity"]
        assert store.detail(c, UUID(draft["id"])) == frozen
    assert snapshot(database) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("baseline_identity", "c" * 64),
        ("symbol", "BTCUSDm"),
        ("timeframe", "M5"),
        ("broker", "Other broker"),
    ],
)
def test_baseline_binding_rejection(
    database: Engine, tmp_path: Path, field: str, value: str
) -> None:
    d = fixture_definition(database, tmp_path)
    changed = d.model_dump(mode="json")
    changed[field] = value
    before = snapshot(database)
    with database.begin() as c, pytest.raises(ValueError, match="BINDING_MISMATCH"):
        store.save(c, ExperimentDefinition.model_validate(changed))
    assert snapshot(database) == before


def test_definition_http_same_origin_and_no_execution(database: Engine, tmp_path: Path) -> None:
    d = fixture_definition(database, tmp_path)
    before = snapshot(database)
    server = ExperimentServer(
        database, tmp_path / "artifacts", Path("dashboard/dist"), 0, root=tmp_path / "evidence"
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        headers = {"Content-Type": "application/json", "X-Workbench-Request": "1"}
        client.request(
            "POST",
            "/workbench-api/experiments",
            d.model_dump_json(),
            {**headers, "Origin": "https://external.invalid"},
        )
        response = client.getresponse()
        assert response.status == 403
        response.read()
        client.request("POST", "/workbench-api/experiments", d.model_dump_json(), headers)
        response = client.getresponse()
        assert response.status == 201
        record = json.loads(response.read())
        key = record["id"]
        client.request(
            "POST",
            f"/workbench-api/experiments/{key}/freeze",
            json.dumps({"confirmed": True}),
            headers,
        )
        response = client.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["state"] == "FROZEN"
        client.request(
            "POST",
            f"/workbench-api/experiments/{key}/unlock-oos",
            json.dumps({"confirmed": True}),
            headers,
        )
        response = client.getresponse()
        assert response.status == 409
        assert json.loads(response.read())["event"] == "PROTOCOL_VIOLATION"
        client.request("GET", f"/workbench-api/experiments?project_id={d.project_id}")
        response = client.getresponse()
        assert response.status == 200
        saved = json.loads(response.read())["items"]
        assert saved[0]["execution_enabled"] is False
        client.request("GET", f"/workbench-api/experiments/{key}/oos-metrics")
        response = client.getresponse()
        assert response.status == 400
        response.read()
        client.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert snapshot(database) == before
