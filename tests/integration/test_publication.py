"""Offline publication is additive, deterministic and read-only for old evidence."""

import json
import re
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select

from tests.integration import test_installed_execution as installed_tests
from tests.integration.test_baseline import migration, ready, server  # noqa: F401
from tests.phase5b_helpers import report as original_report
from tests.test_phase5b_tick_evidence import assess, source
from trading_ecosystem.tester import evidence, process, publication, readiness, store
from trading_ecosystem.tester.contracts import State
from trading_ecosystem.tester.service import Service

database = installed_tests.database


@pytest.mark.parametrize("quality", ["100% real ticks", "50% real ticks", "UNKNOWN"])
@pytest.mark.parametrize("zero_trades", [False, True])
def test_publication_preserves_history_and_requires_proof(
    database: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    quality: str,
    zero_trades: bool,
) -> None:
    if zero_trades:
        from tests import test_phase5b_tick_evidence as fixtures

        def zero_report(expert: str) -> bytes:
            raw = original_report(expert).decode()
            labels = [
                "Total Trades",
                "Short Trades (won %)",
                "Long Trades (won %)",
                "Profit Trades (% of total)",
                "Loss Trades (% of total)",
            ]
            for label in labels:
                raw = re.sub(re.escape(label) + r":</td><td>[^<]*", label + ":</td><td>0", raw)
            return raw.encode()

        monkeypatch.setattr(fixtures, "report", zero_report)
    run = ready(database, tmp_path / "artifacts")
    root = tmp_path / "source"
    blocked = source(
        root,
        run.model_copy(
            update={
                "status": State.BLOCKED_REAL_TICKS_UNAVAILABLE,
                "exit_code": 0,
            }
        ),
        quality,
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
    record = assess(root, blocked)
    path = tmp_path / "assessment.json"
    evidence.write_json(path, record)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    tables = [store.runs, store.results, readiness.configurations, readiness.authorizations]

    def snapshot() -> dict[str, Any]:
        with database.connect() as conn:
            return {
                t.name: list(conn.execute(select(t).order_by(t.c.id)).mappings()) for t in tables
            }

    old = snapshot()

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Publication cannot execute or create a run")

    monkeypatch.setattr(process, "execute", forbidden)
    monkeypatch.setattr(Service, "start", forbidden)
    monkeypatch.setattr(store, "create", forbidden)
    if quality != "100% real ticks":
        with database.begin() as conn, pytest.raises(ValueError, match="NOT_ELIGIBLE"):
            publication.publish(conn, run.config.baseline_run_id, root, path)
    else:
        with database.begin() as conn:
            first = publication.publish(conn, run.config.baseline_run_id, root, path)
        with database.begin() as conn:
            assert publication.publish(conn, run.config.baseline_run_id, root, path) == first
            assert publication.read(conn, run.config.baseline_run_id) == first
            assert store.result(conn, run.config.baseline_run_id) is None
        assert first["reconciliation_identity"] == record["reconciliation_identity"]
        assert first["execution_outcome"] == "BLOCKED_REAL_TICKS_UNAVAILABLE"
        assert first["stored_utf8_report_identity"] == evidence.file_identity(root / "report.htm")
        assert first["native_source_verification"].endswith("ORIGINAL_BYTES_NOT_RETAINED")
        if zero_trades:
            assert first["metrics"]["total_trades"] == 0
            assert first["metrics"]["win_rate"] is None
            assert first["metrics"]["profit_factor"] is None
            assert first["metrics"]["expected_payoff"] is None
        else:
            assert first["metrics"] == record["offline_normalization"]["metrics"]
        assert set(first["metrics"]) == set(record["offline_normalization"]["metrics"])
        with server(database, tmp_path / "http") as instance:
            client = HTTPConnection("127.0.0.1", instance.server_port, timeout=10)
            client.request("GET", "/workbench-api/baselines/" + str(run.config.baseline_run_id))
            response = client.getresponse()
            assert response.status == 200
            detail = json.loads(response.read())
            assert detail["publication"] == first
            assert detail["result"] is None
            assert detail["run"]["status"] == "BLOCKED_REAL_TICKS_UNAVAILABLE"
            client.close()
        record["configuration_identity"] = "f" * 64
        path.write_text(json.dumps(record))
        with database.begin() as conn, pytest.raises(ValueError, match="MISMATCH"):
            publication.publish(conn, run.config.baseline_run_id, root, path)
    assert old == snapshot()
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}
