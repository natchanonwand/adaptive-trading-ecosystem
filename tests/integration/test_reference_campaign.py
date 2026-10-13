"""Disposable PostgreSQL reference pre-registration; no native execution."""

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, select

from tests.integration import test_experiment_campaigns as isolated
from tests.integration.test_baseline import migration  # noqa: F401
from tests.integration.test_experiment_campaigns import campaign_migration  # noqa: F401
from tests.test_reference_campaign import fixture
from trading_ecosystem.experiments import authorization, store
from trading_ecosystem.experiments import campaign_store as ledger
from trading_ecosystem.experiments.campaign_runner import Runner
from trading_ecosystem.experiments.contracts import digest
from trading_ecosystem.experiments.reference_contract import parse_definition
from trading_ecosystem.tester import readiness
from trading_ecosystem.tester import store as baseline
from trading_ecosystem.workbench import store as onboarding
from trading_ecosystem.workbench.contracts import CreateProject

database = isolated.database


def prepared(database: Engine, tmp_path: Path) -> UUID:
    with database.begin() as conn:
        artifact = onboarding.register_artifact(
            conn, tmp_path, "reference.ex5", "EA", b"synthetic only"
        )
        project = onboarding.create_project(
            conn,
            tmp_path,
            CreateProject.model_validate(
                dict(
                    project_id=str(uuid4()),
                    project_name="Reference test",
                    source_type="PROJECT_OWNED_REFERENCE",
                    candidate=dict(
                        artifact_id=str(artifact.artifact_id), source_reference="PROJECT_SOURCE"
                    ),
                    broker_binding=dict(
                        broker_name="Exness",
                        canonical_asset="XAUUSD",
                        broker_symbol="XAUUSDm",
                        timeframe="M5",
                        symbol_confirmed=True,
                    ),
                )
            ),
        )
        config = readiness.save_configuration(
            conn,
            tmp_path,
            readiness.BaselineConfiguration(
                configuration_id=uuid4(),
                project_id=project.project_id,
                confirmed=True,
                parameters=dict(
                    symbol="XAUUSDm",
                    timeframe="M5",
                    from_date="2026-01-01",
                    to_date="2026-06-30",
                    initial_deposit="300",
                    currency="USD",
                    leverage=100,
                    timeout_seconds=600,
                ),
            ),
        )
        data = fixture().model_dump(mode="json")
        data.update(
            project_id=str(project.project_id),
            candidate_id=str(project.candidate_id),
            baseline_configuration_id=config["specification"]["configuration_id"],
            baseline_identity=config["configuration_identity"],
        )
        d = parse_definition(data)
        saved = store.save(conn, d)
        store.freeze(conn, UUID(saved["id"]))
        body = ledger.create(conn, UUID(saved["id"]), d.identity)
    return UUID(body["id"])


def test_no_authorization_no_reservation(database: Engine, tmp_path: Path) -> None:
    key = prepared(database, tmp_path)
    fake = isolated.Fake()
    with pytest.raises(ValueError, match="NOT_AUTHORIZED"):
        Runner(database, fake).run(key)
    with database.connect() as conn:
        body = ledger.read(conn, key)
    assert body["consumed_executions"] == 0 and body["runs"] == [] and not fake.calls


def test_authorization_separate_from_start_and_immutable(
    database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = prepared(database, tmp_path)
    with database.connect() as conn:
        body = ledger.read(conn, key)
    content = authorization.capability(body, {"synthetic_demo": True})

    def reviewed(*args: Any) -> dict[str, Any]:
        return dict(review_identity=digest(content), content=content, authorization_eligible=True)

    monkeypatch.setattr(authorization, "review", reviewed)
    with database.begin() as conn:
        with pytest.raises(ValueError, match="EXPLICIT"):
            authorization.authorize(conn, key, tmp_path, tmp_path, "incorrect", True)
        result = authorization.authorize(conn, key, tmp_path, tmp_path, digest(content), True)
        assert result["state"] == "AUTHORIZED"
        assert ledger.read(conn, key)["runs"] == []
        authorization.authorize(conn, key, tmp_path, tmp_path, digest(content), True)
        assert (
            len(
                [
                    e
                    for e in ledger.read(conn, key)["audit"]
                    if e["event"] == "EXPLICIT_EXECUTION_AUTHORIZATION"
                ]
            )
            == 1
        )


def test_reference_runner_top_two_and_budget(database: Engine, tmp_path: Path) -> None:
    key = prepared(database, tmp_path)
    with database.begin() as conn:
        body = ledger.read(conn, key, True)
        content = authorization.capability(body, {"synthetic_demo": True})
        body["execution_authorization"] = dict(
            state="AUTHORIZED", content=content, identity=digest(content)
        )
        ledger.persist(conn, body)
        before = list(conn.execute(select(baseline.runs.c.body)).scalars())

    class Fake(isolated.Fake):
        def execute(self, *args: Any, **kwargs: Any) -> tuple[str, dict[str, Any] | None]:
            status, result = super().execute(*args, **kwargs)
            assert result is not None
            result["metrics"] = {"NET_PROFIT": "10", "TRADE_COUNT": "10", "PROFIT_FACTOR": "1"}
            return status, result

    fake = Fake()
    Runner(database, fake).run(key)
    with database.connect() as conn:
        body = ledger.read(conn, key)
        assert list(conn.execute(select(baseline.runs.c.body)).scalars()) == before
    assert len(fake.calls) == 11 and body["consumed_executions"] == 11
    assert len(body["selection"]["selected"]) == 2 and body["status"] == "COMPLETE"
    assert all(r["purpose"] != "LOCKED_OOS" for r in body["runs"])
    assert (
        body["selection"]["selected"]
        == sorted(c["identity"] for c in body["plan"]["candidates"])[:2]
    )
