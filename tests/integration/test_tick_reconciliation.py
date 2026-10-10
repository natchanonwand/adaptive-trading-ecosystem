"""PostgreSQL immutability and synthetic service coverage; never execute a native EA."""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select

from tests.integration import test_installed_execution as installed_tests
from tests.integration.test_baseline import finish, migration, ready, simulated  # noqa: F401
from tests.phase5b_helpers import environment
from tests.test_phase5b_tick_evidence import assess, source
from trading_ecosystem.tester import process, readiness, reconciliation, store
from trading_ecosystem.tester.adapter import Adapter
from trading_ecosystem.tester.contracts import State
from trading_ecosystem.tester.service import Service

database = installed_tests.database


def test_reconciliation_never_mutates_or_executes(
    database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = ready(database, tmp_path / "artifacts")
    root = tmp_path / "preserved"
    blocked = source(
        root,
        run.model_copy(update={"status": State.BLOCKED_REAL_TICKS_UNAVAILABLE, "exit_code": 0}),
    )
    with database.begin() as conn:
        for state in (State.QUEUED, State.PREPARING, State.RUNNING):
            store.advance(conn, run.config.baseline_run_id, state)
        blocked = store.advance(
            conn,
            run.config.baseline_run_id,
            State.BLOCKED_REAL_TICKS_UNAVAILABLE,
            exit_code=0,
            evidence_identity=blocked.evidence_identity,
        )
    tables = [store.runs, store.results, readiness.configurations, readiness.authorizations]

    def snapshot() -> dict[str, Any]:
        with database.connect() as conn:
            return {
                t.name: list(conn.execute(select(t).order_by(t.c.id)).mappings()) for t in tables
            }

    before = snapshot()

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Offline reconciliation may not execute or create a run")

    monkeypatch.setattr(process, "execute", forbidden)
    monkeypatch.setattr(Service, "start", forbidden)
    monkeypatch.setattr(store, "create", forbidden)
    record = assess(root, blocked)
    reconciliation.persist(tmp_path / "derived", record)
    assert snapshot() == before
    assert record["offline_normalization"] is not None
    assert record["baseline_result_created"] is False
    with database.connect() as conn:
        assert store.get(conn, run.config.baseline_run_id) == blocked
        assert store.result(conn, run.config.baseline_run_id) is None


@pytest.mark.parametrize(
    "quality,log,status",
    [
        ("100% real ticks", "generating based on real ticks", State.COMPLETE),
        ("100%", "generating based on real ticks", State.REAL_TICK_EVIDENCE_UNVERIFIED),
        ("73% real ticks", "generating based on real ticks", State.REAL_TICK_COVERAGE_PARTIAL),
    ],
)
def test_service_uses_report_without_downgrading_fidelity(
    database: Engine, tmp_path: Path, quality: str, log: str, status: State
) -> None:
    run = ready(database, tmp_path / "artifacts")
    fake = simulated("success")

    def native(*args: Any) -> process.Outcome:
        outcome = fake(*args)
        runtime = args[2]
        (runtime / "logs/tester.log").write_text(log)
        path = next(runtime.glob("*.htm"))
        path.write_bytes(
            path.read_bytes().replace(b"<td>100%</td>", f"<td>{quality}</td>".encode())
        )
        return outcome

    service = Service(
        database,
        tmp_path / "artifacts",
        tmp_path / "evidence",
        Adapter(environment(tmp_path), native),
    )
    final = finish(service, run.config.baseline_run_id)
    assert final.status == status
    with database.connect() as conn:
        assert (store.result(conn, run.config.baseline_run_id) is not None) == (
            status == State.COMPLETE
        )
