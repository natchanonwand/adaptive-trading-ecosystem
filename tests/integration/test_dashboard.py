"""Read-only UI queries against the actual migrated PostgreSQL API."""

import os
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import closing
from http.client import HTTPConnection
from threading import Thread
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text, update

from tests.integration.test_monitoring import (
    event,
    http,
)
from tests.integration.test_monitoring import (
    monitoring_migration as monitoring_migration,
)
from tests.integration.test_monitoring import (
    scope as scope,
)
from trading_ecosystem.dashboard_api import queries
from trading_ecosystem.dashboard_api.server import DashboardServer
from trading_ecosystem.monitoring import schema
from trading_ecosystem.monitoring.contracts import EventType, PositionView, Scope
from trading_ecosystem.monitoring.journal import TelemetryJournal


@pytest.fixture
def server(database: Engine) -> Iterator[DashboardServer]:
    with DashboardServer(database, 0) as instance:
        thread = Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        try:
            yield instance
        finally:
            instance.shutdown()
            thread.join(5)
            assert not thread.is_alive()


def test_stream_catalog_and_atomic_initial_snapshot(
    server: DashboardServer, database: Engine, scope: Scope
) -> None:
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        journal.append(event(scope, EventType.ACCOUNT_SNAPSHOT))
        journal.append(event(scope, EventType.PORTFOLIO_SNAPSHOT, 2))
    status, catalog = http(server, "/api/v1/dashboard/streams?limit=500")
    assert status == 200 and any(r["stream_id"] == str(scope.stream_id) for r in catalog["items"])
    status, initial = http(server, f"/api/v1/dashboard/snapshot?stream_id={scope.stream_id}")
    assert status == 200 and initial["cursor"] == 2
    assert initial["scope"] == scope.model_dump(mode="json")
    assert initial["views"]["account"]["items"][0]["values"]["balance"] == "10000"
    assert initial["views"]["account"]["items"][0]["occurred_at"].endswith("+00:00")
    assert initial["events"][-1]["sequence"] == 2
    with database.begin() as conn:
        TelemetryJournal(conn).append(event(scope, EventType.SYSTEM_HEALTH, 3))
    status, resumed = http(
        server, f"/api/v1/stream?stream_id={scope.stream_id}&after=2&follow=false"
    )
    assert status == 200 and resumed.startswith("id: 3\n")


def test_snapshot_uses_one_repeatable_read_boundary(database: Engine, scope: Scope) -> None:
    with database.begin() as conn:
        TelemetryJournal(conn).append(event(scope, EventType.ACCOUNT_SNAPSHOT))
    with database.begin() as reader:
        reader.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        first = queries.snapshot(reader, scope.stream_id)
        with database.begin() as writer:
            TelemetryJournal(writer).append(event(scope, EventType.ACCOUNT_SNAPSHOT, 2))
        assert queries.snapshot(reader, scope.stream_id) == first


@pytest.mark.parametrize("unknown", [False, True])
def test_calendar_sums_reported_values_and_keeps_unknowns(
    database: Engine, server: DashboardServer, scope: Scope, unknown: bool
) -> None:
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        for i, pnl in enumerate(("0.10", "0.20")):
            seq = i * 2 + 1
            opened = event(scope, EventType.POSITION_OPENED, seq)
            assert isinstance(opened.payload, PositionView)
            episode = uuid4()
            opened = opened.model_copy(
                update={"payload": opened.payload.model_copy(update={"episode_id": episode})}
            )
            journal.append(opened)
            closed = event(scope, EventType.POSITION_CLOSED, seq + 1)
            assert isinstance(closed.payload, PositionView)
            trade = {
                "episode_id": episode,
                "closed_at": closed.occurred_at,
                "gross_pnl": pnl,
                "net_pnl": None if unknown and i == 1 else pnl,
                "net_r": None,
                "commission": "0",
                "financing": "0",
                "spread_cost": None,
                "outcome": "WIN",
                "complete": False,
            }
            closed = closed.model_copy(
                update={
                    "payload": closed.payload.model_copy(
                        update={"episode_id": episode, "trade": trade}
                    )
                }
            )
            journal.append(closed)
    status, result = http(
        server,
        f"/api/v1/dashboard/calendar?stream_id={scope.stream_id}&start=2026-09-01&end=2026-10-01",
    )
    assert status == 200 and len(result["days"]) == 30
    day = next(d for d in result["days"] if d["date"] == "2026-09-16")
    assert day["net_pnl"] == (None if unknown else "0.30")
    assert day["trade_count"] == 2 and day["wins"] == 2
    assert day["commission"] == "0" and day["spread_cost"] is None and day["net_r"] is None
    assert day["max_intraday_drawdown"] is None
    assert result["days"][0]["trade_count"] is None and result["days"][0]["net_pnl"] is None
    _, first_page = http(server, f"/api/v1/dashboard/trades?stream_id={scope.stream_id}&limit=1")
    assert first_page["has_more"] and first_page["next_cursor"] == 2
    _, second_page = http(
        server, f"/api/v1/dashboard/trades?stream_id={scope.stream_id}&limit=1&after=2"
    )
    assert second_page["items"][0]["sequence"] == 4 and second_page["next_cursor"] is None


def test_history_bounded_latest_and_position_filters(
    database: Engine, server: DashboardServer, scope: Scope
) -> None:
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        for seq in range(1, 4):
            journal.append(event(scope, EventType.ACCOUNT_SNAPSHOT, seq))
        journal.append(event(scope, EventType.POSITION_OPENED, 4))
    status, result = http(server, f"/api/v1/dashboard/history?stream_id={scope.stream_id}&limit=2")
    assert status == 200 and [r["sequence"] for r in result["items"]] == [2, 3]
    assert result["has_more"] is True
    status, filtered = http(
        server, f"/api/v1/dashboard/positions?stream_id={scope.stream_id}&symbol=XAUUSD"
    )
    assert status == 200 and filtered["items"] == []
    status, filtered = http(
        server,
        f"/api/v1/dashboard/positions?stream_id={scope.stream_id}&symbol=BTCUSD&environment=BACKTEST",
    )
    assert status == 200 and len(filtered["items"]) == 1


def test_view_corruption_isolated_and_collection_fails_closed(
    database: Engine, server: DashboardServer, scope: Scope
) -> None:
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        journal.append(event(scope, EventType.ACCOUNT_SNAPSHOT))
        journal.append(event(scope, EventType.RISK_APPROVED, 2))
        conn.execute(
            update(schema.risk_projection)
            .where(schema.risk_projection.c.stream_id == scope.stream_id)
            .values(body={})
        )
    status, result = http(server, f"/api/v1/dashboard/snapshot?stream_id={scope.stream_id}")
    assert status == 200 and result["views"]["risk"] is None
    assert result["views"]["account"]["items"] and "risk" in result["errors"]


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "?stream_id=bad",
        "?stream_id={s}&limit=501",
        "?stream_id={s}&after=-1",
        "?stream_id={s}&limit=2&limit=3",
        "?stream_id={s}&start=bad&end=bad",
        "?stream_id={s}&start=2026-01-01&end=2028-01-01",
        "?stream_id={s}&unknown=1",
    ],
)
def test_dashboard_invalid_queries(server: DashboardServer, scope: Scope, suffix: str) -> None:
    assert http(server, "/api/v1/dashboard/trades" + suffix.format(s=scope.stream_id))[0] == 400


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_new_endpoints_cannot_write(server: DashboardServer, method: str) -> None:
    assert http(server, "/api/v1/dashboard/snapshot", method)[0] == 405


def test_new_endpoints_keep_origin_guard(server: DashboardServer) -> None:
    assert (
        http(server, "/api/v1/dashboard/streams", headers={"Origin": "https://example.invalid"})[0]
        == 403
    )


def test_stream_catalog_paginates_without_cross_scope_data(
    database: Engine, server: DashboardServer, scope: Scope
) -> None:
    with database.begin() as conn:
        TelemetryJournal(conn).append(event(scope))
        other = scope.model_copy(update={"run_id": uuid4()})
        TelemetryJournal(conn).append(event(other))
    status, first = http(server, "/api/v1/dashboard/streams?limit=1")
    assert status == 200 and len(first["items"]) == 1 and first["next_cursor"]
    status, second = http(server, "/api/v1/dashboard/streams?limit=1&after=" + first["next_cursor"])
    assert status == 200 and second["items"][0]["stream_id"] != first["items"][0]["stream_id"]


def test_original_health_endpoint_remains_available(server: DashboardServer) -> None:
    with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as client:
        client.request("GET", "/health")
        assert client.getresponse().status == 200


def test_typescript_client_against_actual_monitoring_api(
    database: Engine, server: DashboardServer, scope: Scope
) -> None:
    with database.begin() as conn:
        TelemetryJournal(conn).append(event(scope, EventType.ACCOUNT_SNAPSHOT))
    environment = dict(os.environ)
    environment["DASHBOARD_TEST_API"] = f"http://127.0.0.1:{server.server_port}"
    environment["DASHBOARD_TEST_STREAM"] = str(scope.stream_id)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    assert npm is not None, "Node/npm required for the Phase 3.6 API integration"
    result = subprocess.run(
        [npm, "run", "test"],
        cwd="dashboard",
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
