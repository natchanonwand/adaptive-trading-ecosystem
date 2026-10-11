"""Fresh PostgreSQL campaign ledger tests using deterministic, non-native boundaries."""

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Engine, select, text

from tests.integration import test_experiments as isolated
from tests.integration.test_baseline import migration  # noqa: F401
from tests.integration.test_experiments import fixture_definition, snapshot
from trading_ecosystem.experiments import campaign_store as ledger
from trading_ecosystem.experiments import store
from trading_ecosystem.experiments.campaign_runner import Runner
from trading_ecosystem.experiments.contracts import ExperimentDefinition

database = isolated.database


@pytest.fixture(scope="module", autouse=True)
def campaign_migration(database: Engine, migration: None) -> None:  # noqa: F811
    env = dict(os.environ, TE_DATABASE_URL=database.url.render_as_string(hide_password=False))
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic-campaigns.ini", "upgrade", "head"],
            env=env,
            capture_output=True,
        )
        assert result.returncode == 0, "Campaign migration failed (private details suppressed)"
    with database.connect() as conn:
        assert (
            conn.execute(
                text("SELECT version_num FROM workbench.campaign_alembic_version")
            ).scalar_one()
            == "0001_campaigns"
        )
        assert (
            conn.execute(
                text("SELECT version_num FROM workbench.baseline_alembic_version")
            ).scalar_one()
            == "0004_experiment_definitions"
        )


def create(
    database: Engine, tmp_path: Path, *, budget: int = 6
) -> tuple[UUID, ExperimentDefinition]:
    d = fixture_definition(database, tmp_path)
    data = d.model_dump(mode="json")
    data["budget"].update(method="GRID", random_seed=None, maximum_native_executions=budget)
    data["objectives"] = [{"metric": "TRADE_COUNT", "direction": "MAXIMIZE", "definition": "count"}]
    data["constraints"][0]["threshold"] = "0"
    d = ExperimentDefinition.model_validate(data)
    with database.begin() as conn:
        record = store.save(conn, d)
        store.freeze(conn, UUID(record["id"]))
        campaign = ledger.create(conn, UUID(record["id"]), d.identity)
    return UUID(campaign["id"]), d


class Fake:
    def __init__(self, mode: str = "COMPLETE") -> None:
        self.calls: list[dict[str, Any]] = []
        self.mode = mode
        self.started = Event()

    def validate(self, definition: ExperimentDefinition) -> None:
        pass

    def recover(self, run: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        return "INTERRUPTED_NOT_RETRIED", None

    def execute(
        self,
        definition: ExperimentDefinition,
        candidate: dict[str, Any],
        run: dict[str, Any],
        deadline: datetime,
        cancelled: Event,
    ) -> tuple[str, dict[str, Any] | None]:
        assert run["purpose"] in {"DEVELOPMENT", "VALIDATION"}
        assert run["end"] <= str(definition.split_plan.splits[2].start)
        self.calls.append(dict(run))
        self.started.set()
        if self.mode == "CRASH":
            raise RuntimeError("synthetic interruption")
        if self.mode == "WAIT":
            assert cancelled.wait(5)
            return "CANCELLED", None
        if self.mode != "COMPLETE":
            return self.mode, None
        return "COMPLETE", {
            "metrics": {"TRADE_COUNT": "0", "PROFIT_FACTOR": None},
            "baseline_run_id": run["id"],
            "evidence_identity": "a" * 64,
            "result_identity": "b" * 64,
        }


def read(database: Engine, key: UUID) -> dict[str, Any]:
    with database.connect() as conn:
        return ledger.read(conn, key)


def test_frozen_only_and_identity(database: Engine, tmp_path: Path) -> None:
    d = fixture_definition(database, tmp_path)
    with database.begin() as conn:
        record = store.save(conn, d)
        with pytest.raises(ValueError, match="FROZEN"):
            ledger.create(conn, UUID(record["id"]), d.identity)
        store.freeze(conn, UUID(record["id"]))
        with pytest.raises(ValueError, match="IDENTITY"):
            ledger.create(conn, UUID(record["id"]), "c" * 64)


def test_complete_idempotent_zero_trades_and_no_historical_mutation(
    database: Engine, tmp_path: Path
) -> None:
    key, d = create(database, tmp_path)
    before = snapshot(database)
    fake = Fake()
    runner = Runner(database, fake)
    runner.run(key)
    body = read(database, key)
    assert body["status"] == "COMPLETE" and len(fake.calls) == 6
    assert [r["purpose"] for r in body["runs"]] == ["DEVELOPMENT"] * 3 + ["VALIDATION"] * 3
    assert body["selection_identity"] and len(body["selection"]["selected"]) == 3
    assert [e["event"] for e in body["audit"]].index("DEVELOPMENT_SELECTION_FROZEN") < [
        e["event"] for e in body["audit"]
    ].index("COMPLETE")
    Runner(database, fake).run(key)
    assert read(database, key) == body and len(fake.calls) == 6
    with database.begin() as conn:
        assert ledger.create(conn, UUID(body["definition_id"]), d.identity) == body
    assert snapshot(database) == before


def test_native_budget_preserved_across_resume(database: Engine, tmp_path: Path) -> None:
    key, _ = create(database, tmp_path, budget=3)
    fake = Fake()
    Runner(database, fake).run(key)
    body = read(database, key)
    assert body["status"] == "BUDGET_EXHAUSTED" and body["consumed_executions"] == 3
    assert body["selection_identity"]
    Runner(database, fake).run(key)
    assert len(fake.calls) == 3


@pytest.mark.parametrize(
    "status", ["TIMEOUT", "REPORT_PARSE_FAILED", "INITIALIZATION_FAILED", "TESTER_FAILED"]
)
def test_individual_failure_does_not_retry_or_abort_remaining_development(
    database: Engine, tmp_path: Path, status: str
) -> None:
    key, _ = create(database, tmp_path)
    fake = Fake(status)
    Runner(database, fake).run(key)
    body = read(database, key)
    assert len(fake.calls) == 3 and body["status"] == "NO_ELIGIBLE_SELECTION"
    assert all(r["status"] == status for r in body["runs"])


def test_crash_reserved_slot_never_replayed(database: Engine, tmp_path: Path) -> None:
    key, _ = create(database, tmp_path)
    with pytest.raises(RuntimeError, match="interruption"):
        Runner(database, Fake("CRASH")).run(key)
    old = read(database, key)
    fake = Fake()
    Runner(database, fake).run(key)
    body = read(database, key)
    assert old["plan"] == body["plan"]
    assert body["runs"][0]["status"] == "INTERRUPTED_NOT_RETRIED"
    assert old["runs"][0]["id"] not in [r["id"] for r in fake.calls]
    assert body["consumed_executions"] == 5


def test_cancel_owned_run_and_global_concurrency(database: Engine, tmp_path: Path) -> None:
    key, _ = create(database, tmp_path)
    fake = Fake("WAIT")
    thread = Thread(target=Runner(database, fake).run, args=(key,))
    thread.start()
    assert fake.started.wait(5)
    with pytest.raises(ValueError, match="BUSY"):
        Runner(database, Fake()).run(key)
    with database.begin() as conn:
        ledger.cancel(conn, key)
    thread.join(8)
    assert not thread.is_alive()
    body = read(database, key)
    assert body["status"] == "CANCELLED" and body["consumed_executions"] == 1
    assert len(body["runs"]) == 1


def test_cancel_before_start_never_calls_boundary(database: Engine, tmp_path: Path) -> None:
    key, _ = create(database, tmp_path)
    with database.begin() as conn:
        ledger.cancel(conn, key)
    fake = Fake()
    Runner(database, fake).run(key)
    assert fake.calls == [] and read(database, key)["consumed_executions"] == 0


def test_persisted_deadline_is_not_reset(database: Engine, tmp_path: Path) -> None:
    key, _ = create(database, tmp_path)
    with database.begin() as conn:
        body = ledger.read(conn, key, True)
        body.update(
            started_at=datetime(2020, 1, 1, tzinfo=UTC).isoformat(),
            deadline=datetime(2020, 1, 2, tzinfo=UTC).isoformat(),
        )
        ledger.persist(conn, body)
    fake = Fake()
    Runner(database, fake).run(key)
    assert fake.calls == [] and read(database, key)["status"] == "BUDGET_EXHAUSTED"


def test_ledger_tampering_fails_closed(database: Engine, tmp_path: Path) -> None:
    key, _ = create(database, tmp_path)
    with database.begin() as conn:
        payload = conn.execute(
            select(ledger.records.c.body).where(ledger.records.c.id == str(key))
        ).scalar_one()
        payload["content"]["consumed_executions"] = -1
        conn.execute(
            ledger.records.update().where(ledger.records.c.id == str(key)).values(body=payload)
        )
    with pytest.raises(ValueError, match="LEDGER_IDENTITY"):
        Runner(database, Fake()).run(key)


def test_invalid_success_result_is_not_selected(database: Engine, tmp_path: Path) -> None:
    key, _ = create(database, tmp_path)

    class Invalid(Fake):
        def execute(
            self,
            definition: ExperimentDefinition,
            candidate: dict[str, Any],
            run: dict[str, Any],
            deadline: datetime,
            cancelled: Event,
        ) -> tuple[str, dict[str, Any] | None]:
            status, value = super().execute(definition, candidate, run, deadline, cancelled)
            assert value is not None
            value["result_identity"] = "missing"
            return status, value

    Runner(database, Invalid()).run(key)
    body = read(database, key)
    assert all(r["status"] == "RESULT_VALIDATION_FAILED" for r in body["runs"])
    assert body["selection"]["selected"] == []


def test_validation_cannot_change_candidates_or_selection(database: Engine, tmp_path: Path) -> None:
    key, _ = create(database, tmp_path)

    class ValidationFailure(Fake):
        def execute(
            self,
            definition: ExperimentDefinition,
            candidate: dict[str, Any],
            run: dict[str, Any],
            deadline: datetime,
            cancelled: Event,
        ) -> tuple[str, dict[str, Any] | None]:
            if run["purpose"] == "VALIDATION":
                assert read(database, key)["selection_identity"]
                return "TIMEOUT", None
            return super().execute(definition, candidate, run, deadline, cancelled)

    before = read(database, key)["plan"]
    Runner(database, ValidationFailure()).run(key)
    body = read(database, key)
    assert body["plan"] == before and len(body["runs"]) == 6
    assert body["status"] == "PARTIAL" and len(body["selection"]["selected"]) == 3


def test_campaign_http_creation_is_not_execution_and_oos_denial_is_audited(
    database: Engine, tmp_path: Path
) -> None:
    import json
    from http.client import HTTPConnection

    from trading_ecosystem.experiments.campaign_api import CampaignServer, install

    key, d = create(database, tmp_path)
    before = snapshot(database)
    server = CampaignServer(
        database, tmp_path / "artifacts", Path("dashboard/dist"), 0, root=tmp_path / "evidence"
    )
    install(server)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        headers = {"Content-Type": "application/json", "X-Workbench-Request": "1"}
        client.request(
            "POST",
            "/workbench-api/campaigns",
            json.dumps(
                {
                    "definition_id": read(database, key)["definition_id"],
                    "definition_identity": d.identity,
                    "confirmed": True,
                }
            ),
            headers,
        )
        response = client.getresponse()
        assert response.status == 201 and json.loads(response.read())["status"] == "CREATED"
        client.request("GET", f"/workbench-api/campaigns/{key}")
        response = client.getresponse()
        assert response.status == 200 and json.loads(response.read())["runs"] == []
        client.request(
            "POST", f"/workbench-api/campaigns/{key}/unlock-oos", '{"confirmed":true}', headers
        )
        response = client.getresponse()
        assert response.status == 409
        assert json.loads(response.read())["audit"][-1]["event"] == "PROTOCOL_VIOLATION"
        client.request(
            "POST", f"/workbench-api/campaigns/{key}/start", '{"confirmed":false}', headers
        )
        response = client.getresponse()
        assert response.status == 400
        response.read()
        client.request(
            "POST",
            f"/workbench-api/campaigns/{key}/start",
            '{"confirmed":true}',
            {**headers, "Origin": "https://external.invalid"},
        )
        response = client.getresponse()
        assert response.status == 403
        response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    assert snapshot(database) == before


def test_existing_phase5b_service_and_parser_are_reused_with_fake_native_process(
    database: Engine, tmp_path: Path
) -> None:
    import configparser

    from tests.phase5b_helpers import environment, report
    from trading_ecosystem.experiments.baseline_boundary import BaselineBoundary
    from trading_ecosystem.tester import store as baselines
    from trading_ecosystem.tester.adapter import Adapter
    from trading_ecosystem.tester.process import Outcome
    from trading_ecosystem.tester.service import Service

    original = fixture_definition(database, tmp_path)
    data = original.model_dump(mode="json")
    data["objectives"] = [{"metric": "TRADE_COUNT", "direction": "MAXIMIZE", "definition": "Count"}]
    data["budget"].update(
        method="GRID",
        random_seed=None,
        maximum_configurations=1,
        maximum_native_executions=2,
        maximum_wall_seconds=600,
    )
    data["evidence_classification"] = "EXPLORATORY_GROSS"
    # Cached synthetic history is the existing safe Phase 5B fixture interval.
    data["split_plan"]["splits"] = [
        {"start": "2026-09-01", "end": "2026-09-03", "purpose": "DEVELOPMENT"},
        {"start": "2026-09-03", "end": "2026-09-05", "purpose": "VALIDATION"},
        {"start": "2026-09-05", "end": "2026-09-08", "purpose": "LOCKED_OOS"},
    ]
    d = ExperimentDefinition.model_validate(data)
    calls: list[str] = []

    def process(exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event) -> Outcome:
        assert exe.read_bytes() == b"Synthetic terminal; never execute"
        config = configparser.ConfigParser()
        config.read(Path(args[1].removeprefix("/config:")), encoding="utf-8-sig")
        tester = config["Tester"]
        calls.append(tester["FromDate"])
        assert tester["FromDate"] in {"2026.09.01", "2026.09.03"}
        expert = next((cwd / "MQL5/Experts").glob("*.ex5")).stem
        logs = cwd / "logs"
        logs.mkdir()
        (logs / "tester.log").write_text("100% real ticks")
        raw = (
            report(expert)
            .replace(b"2026.09.01", tester["FromDate"].encode())
            .replace(b"2026.09.08", tester["ToDate"].encode())
        )
        (cwd / (expert + ".htm")).write_bytes(raw)
        return Outcome(0)

    service = Service(
        database,
        tmp_path / "artifacts",
        tmp_path / "evidence",
        Adapter(environment(tmp_path), process),
    )
    with database.begin() as conn:
        record = store.save(conn, d)
        store.freeze(conn, UUID(record["id"]))
        body = ledger.create(conn, UUID(record["id"]), d.identity)
    key = UUID(body["id"])
    Runner(database, BaselineBoundary(service)).run(key)
    body = read(database, key)
    assert body["status"] == "COMPLETE", body["runs"]
    assert len(calls) == 2
    for run in body["runs"]:
        with database.connect() as conn:
            baseline = baselines.get(conn, UUID(run["id"]))
            result = baselines.result(conn, UUID(run["id"]))
        assert (
            result is not None and result.result_identity == run["observation"]["result_identity"]
        )
        assert baseline.evidence_identity == run["observation"]["evidence_identity"]
