"""Real PostgreSQL and loopback HTTP tests, using the existing fresh-database fixture."""

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
from http.client import HTTPConnection, HTTPResponse
from threading import Thread
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, insert, inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.monitoring.fixtures import telemetry
from tests.phase34.fixtures import T, book, economics, fill, quote
from trading_ecosystem.domain.primitives import Asset
from trading_ecosystem.monitoring import schema
from trading_ecosystem.monitoring.adapters import account_view, portfolio_view, position_view
from trading_ecosystem.monitoring.api import MonitoringServer
from trading_ecosystem.monitoring.contracts import (
    Environment,
    EventType,
    HealthView,
    PositionView,
    RiskView,
    Scope,
    TelemetryEvent,
)
from trading_ecosystem.monitoring.journal import TelemetryJournal
from trading_ecosystem.monitoring.queries import TABLES, read_events, read_view
from trading_ecosystem.portfolio.contracts import Observation
from trading_ecosystem.portfolio.fills import apply_fill
from trading_ecosystem.portfolio.projection import project


@pytest.fixture(scope="module", autouse=True)
def monitoring_migration(database: Engine) -> None:
    # Install the additive schema without altering the existing fixture or version assertions.
    environment = dict(os.environ)
    environment["TE_DATABASE_URL"] = database.url.render_as_string(hide_password=False)
    for _ in range(2):
        migrated = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic-monitoring.ini", "upgrade", "head"],
            env=environment,
            capture_output=True,
            check=False,
        )
        if migrated.returncode:
            pytest.fail("monitoring migration failed; driver details suppressed for secret safety")


@pytest.fixture
def scope() -> Scope:
    return Scope(environment=Environment.BACKTEST, account_id=uuid4(), run_id=uuid4())


@pytest.fixture
def server(database: Engine) -> Iterator[MonitoringServer]:
    with MonitoringServer(database, port=0) as instance:
        thread = Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        try:
            yield instance
        finally:
            instance.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


def event(
    scope: Scope, kind: EventType = EventType.SYSTEM_HEALTH, seq: int = 1, **changes: Any
) -> TelemetryEvent:
    return telemetry(kind, seq, scope=scope, **changes)


def http(
    server: MonitoringServer, path: str, method: str = "GET", headers: dict[str, str] | None = None
) -> tuple[int, Any]:
    with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as conn:
        conn.request(method, path, headers=headers or {})
        response = conn.getresponse()
        body = response.read().decode()
        return response.status, json.loads(body) if body.startswith("{") else body


def test_migration_preserves_operational_and_adds_monitoring_tables(database: Engine) -> None:
    inspector = inspect(database)
    names = set(inspector.get_table_names(schema="monitoring"))
    assert {t.name for t in schema.metadata.tables.values()} | {"alembic_version"} == names
    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "journal_events",
        "journal_heads",
    }
    unique = inspector.get_unique_constraints("telemetry_events", schema="monitoring")
    assert any(u["column_names"] == ["event_id"] for u in unique)
    with database.connect() as conn:
        assert conn.execute(
            text("SELECT version_num FROM monitoring.alembic_version")
        ).scalar_one() == ("0001_telemetry")
    assert any(
        u["column_names"] == ["stream_id", "source_instance_id", "source_sequence"] for u in unique
    )


def test_append_replay_duplicate_and_independent_connection(database: Engine, scope: Scope) -> None:
    e = event(scope, EventType.PORTFOLIO_SNAPSHOT)
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        stored = journal.append(e)
        assert journal.append(e) == stored
        before = read_view(conn, "portfolio", scope.stream_id)
        assert len(before["items"]) == 1
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        assert journal.replay(scope.stream_id) == (stored,)
        assert journal.append(e) == stored
        assert read_view(conn, "portfolio", scope.stream_id) == before
        assert journal.rebuild(scope.stream_id) == 1
        assert read_view(conn, "portfolio", scope.stream_id) == before


@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "TRUNCATE"])
def test_raw_journal_is_append_only(database: Engine, scope: Scope, operation: str) -> None:
    with database.begin() as conn:
        TelemetryJournal(conn).append(event(scope))
        with pytest.raises(DBAPIError), conn.begin_nested():
            statement = {
                "UPDATE": "UPDATE monitoring.telemetry_events SET body = body "
                "WHERE stream_id = :stream",
                "DELETE": "DELETE FROM monitoring.telemetry_events WHERE stream_id = :stream",
                "TRUNCATE": "TRUNCATE monitoring.telemetry_events CASCADE",
            }[operation]
            conn.execute(text(statement), {"stream": scope.stream_id})
        assert len(TelemetryJournal(conn).replay(scope.stream_id)) == 1


def test_database_uniqueness_not_only_application_checks(database: Engine, scope: Scope) -> None:
    with database.begin() as conn:
        TelemetryJournal(conn).append(event(scope))
        row = dict(
            conn.execute(select(schema.events).where(schema.events.c.stream_id == scope.stream_id))
            .mappings()
            .one()
        )
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(insert(schema.events).values(**{**row, "sequence": 99}))


@pytest.mark.parametrize("invalid", ["conflict", "gap", "time", "source", "correction"])
def test_invalid_delivery_atomic_failure(database: Engine, scope: Scope, invalid: str) -> None:
    first = event(scope)
    changes: dict[str, Any] = {}
    seq = 2
    if invalid == "conflict":
        seq = 1
        changes["payload"] = HealthView(component="system", state="ERROR")
    elif invalid == "gap":
        seq = 3
    elif invalid == "time":
        changes["occurred_at"] = T
    elif invalid == "source":
        changes["source"] = "EXTERNAL_EA"
    else:
        changes["corrects_event_id"] = uuid4()
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        original = journal.append(first)
        before = read_view(conn, "system", scope.stream_id)
        with pytest.raises(ValueError):
            journal.append(event(scope, seq=seq, **changes))
        assert journal.replay(scope.stream_id) == (original,)
        assert read_view(conn, "system", scope.stream_id) == before
        assert journal.append(event(scope, seq=2)).sequence == 2


def test_correction_appends_without_mutating_original(database: Engine, scope: Scope) -> None:
    first = event(scope)
    correction = event(
        scope,
        seq=2,
        corrects_event_id=first.event_id,
        payload=HealthView(component="system", state="ERROR", detail="correction"),
    )
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        original = journal.append(first)
        journal.append(correction)
        assert journal.replay(scope.stream_id)[0] == original
        assert read_view(conn, "system", scope.stream_id)["items"][0]["values"]["state"] == "ERROR"


def test_sources_order_independently_and_scopes_isolate(database: Engine, scope: Scope) -> None:
    external = uuid4()
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        assert journal.append(event(scope)).sequence == 1
        assert journal.append(event(scope, source_instance_id=external)).sequence == 2
        assert journal.append(event(scope, seq=2)).sequence == 3
        for environment in Environment:
            other = scope.model_copy(update={"environment": environment, "run_id": uuid4()})
            assert journal.append(event(other, source="EXTERNAL_EA")).sequence == 1
            assert len(journal.replay(other.stream_id)) == 1
        assert len(journal.replay(scope.stream_id)) == 3


@pytest.mark.parametrize("kind", [EventType.ACCOUNT_SNAPSHOT, EventType.PORTFOLIO_SNAPSHOT])
def test_late_other_source_cannot_regress_account_state(
    database: Engine, scope: Scope, kind: EventType
) -> None:
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        journal.append(event(scope, kind))
        with pytest.raises(ValueError, match="PROJECTION_TIME_REGRESSION"):
            journal.append(event(scope, kind, source_instance_id=uuid4(), occurred_at=T))
        assert len(journal.replay(scope.stream_id)) == 1


@pytest.mark.parametrize(
    "side,symbol", [("LONG", "BTCUSD"), ("SHORT", "XAUUSD"), ("SHORT", "USTEC100")]
)
def test_position_partial_close_and_nullable_trade(
    database: Engine, scope: Scope, side: str, symbol: str
) -> None:
    opened = event(scope, EventType.POSITION_OPENED, symbol=symbol)
    assert isinstance(opened.payload, PositionView)
    opened = opened.model_copy(update={"payload": opened.payload.model_copy(update={"side": side})})
    updated = event(
        scope,
        EventType.POSITION_UPDATED,
        2,
        symbol=symbol,
        payload=opened.payload.model_copy(
            update={
                "quantity": "0.05",
                "realized_pnl": "2.50",
                "unrealized_pnl": "1.25",
                "updated_at": T + timedelta(seconds=2),
            }
        ),
    )
    closed = event(
        scope,
        EventType.POSITION_CLOSED,
        3,
        symbol=symbol,
        payload=opened.payload.model_copy(
            update={
                "quantity": "0",
                "state": "CLOSED",
                "realized_pnl": "5.25",
                "unrealized_pnl": "0",
                "updated_at": T + timedelta(seconds=3),
            }
        ),
    )
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        journal.append(opened)
        journal.append(updated)
        journal.append(updated)
        rows = read_view(conn, "positions", scope.stream_id)["items"]
        assert len(rows) == 1
        assert rows[0]["values"]["quantity"] == "0.05"
        assert rows[0]["values"]["realized_pnl"] == "2.50"
        assert rows[0]["values"]["unrealized_pnl"] == "1.25"
        journal.append(closed)
        trades = read_view(conn, "trades", scope.stream_id)["items"]
        assert len(trades) == 1 and trades[0]["values"]["net_pnl"] is None
        assert trades[0]["values"]["complete"] is False
        before = {name: read_view(conn, name, scope.stream_id) for name in ("positions", "trades")}
        journal.rebuild(scope.stream_id)
        assert before == {name: read_view(conn, name, scope.stream_id) for name in before}


def test_impossible_position_update_does_not_advance_head(database: Engine, scope: Scope) -> None:
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        with pytest.raises(ValueError, match="WITHOUT_OPEN"):
            journal.append(event(scope, EventType.POSITION_UPDATED))
        assert journal.replay(scope.stream_id) == ()
        assert journal.append(event(scope, EventType.POSITION_OPENED)).sequence == 1


def test_risk_state_history_preserves_last_rejection(database: Engine, scope: Scope) -> None:
    first = event(scope, EventType.RISK_APPROVED)
    assert isinstance(first.payload, RiskView)
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        journal.append(first)
        for seq, state in enumerate(("PAUSE_ENTRIES", "HALT_AND_FLATTEN", "ACTIVE"), 2):
            payload = first.payload.model_copy(
                update={
                    "risk_state": state,
                    "rejection_reasons": ("DAILY_LOSS_LIMIT",) if seq == 2 else (),
                }
            )
            journal.append(event(scope, EventType.RISK_STATE_CHANGED, seq, payload=payload))
            body = read_view(conn, "risk", scope.stream_id)["items"][0]["values"]
            assert body["risk_state"] == state
            assert body["last_rejection_reason"] == ["DAILY_LOSS_LIMIT"]
            assert body["last_state_change"] == (T + timedelta(seconds=seq)).isoformat()
        before = read_view(conn, "risk", scope.stream_id)
        journal.rebuild(scope.stream_id)
        assert read_view(conn, "risk", scope.stream_id) == before


def test_external_ea_metadata_without_internal_strategy(database: Engine, scope: Scope) -> None:
    live = scope.model_copy(update={"environment": Environment.LIVE})
    e = event(
        live,
        EventType.POSITION_OPENED,
        source="EXTERNAL_EA",
        strategy_id=None,
        magic_number=123,
        comment="<untrusted>fixture</untrusted>",
        broker_ticket="EA-17",
    )
    with database.begin() as conn:
        TelemetryJournal(conn).append(e)
        values = read_view(conn, "positions", live.stream_id)["items"][0]["values"]
        assert values["strategy_id"] is None
        assert values["magic_number"] == 123 and values["broker_ticket"] == "EA-17"
        assert values["comment"] == e.comment and values["environment"] == "LIVE"


def test_empty_projection_rebuild_all_views_and_hashes(database: Engine, scope: Scope) -> None:
    kinds = [
        EventType.ACCOUNT_SNAPSHOT,
        EventType.PORTFOLIO_SNAPSHOT,
        EventType.POSITION_OPENED,
        EventType.POSITION_CLOSED,
        EventType.RISK_APPROVED,
        EventType.BROKER_CONNECTED,
        EventType.STRATEGY_STARTED,
    ]
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        assert journal.rebuild(scope.stream_id) == 0
        for seq, kind in enumerate(kinds, 1):
            journal.append(event(scope, kind, seq))
        raw = journal.replay(scope.stream_id)
        before = {name: read_view(conn, name, scope.stream_id) for name in TABLES}
        for table in schema.PROJECTIONS:
            conn.execute(delete(table).where(table.c.stream_id == scope.stream_id))
        assert all(read_view(conn, name, scope.stream_id)["items"] == [] for name in TABLES)
        assert journal.rebuild(scope.stream_id) == len(kinds)
        assert {name: read_view(conn, name, scope.stream_id) for name in TABLES} == before
        assert journal.replay(scope.stream_id) == raw


def test_projection_corruption_detected_and_rebuild_repairs(database: Engine, scope: Scope) -> None:
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        journal.append(event(scope))
        before = read_view(conn, "system", scope.stream_id)
        conn.execute(
            update(schema.system_health_projection)
            .where(schema.system_health_projection.c.stream_id == scope.stream_id)
            .values(body={})
        )
        with pytest.raises(RuntimeError, match="INTEGRITY"):
            read_view(conn, "system", scope.stream_id)
        with pytest.raises(ValueError, match="REBUILD_REQUIRED"):
            journal.append(event(scope, seq=2))
        assert len(journal.replay(scope.stream_id)) == 1
        journal.rebuild(scope.stream_id)
        assert read_view(conn, "system", scope.stream_id) == before


def test_authoritative_multisymbol_partial_close_pipeline(database: Engine, scope: Scope) -> None:
    scope = scope.model_copy(update={"account_id": book().cash.account_id})
    btc = apply_fill(book(), fill())
    gold_economics = economics(instrument_id="fixture-XAU", asset=Asset.XAUUSD)
    both = apply_fill(
        btc,
        fill(
            2,
            asset=Asset.XAUUSD,
            episode_id=UUID(int=35901),
            economics=gold_economics,
            direction="SHORT",
            side="SELL",
            fixed_stop="101",
        ),
    )
    reduced = apply_fill(
        both, fill(3, action="REDUCE", side="SELL", quantity="0.05", actual_price="101")
    )
    initial = Observation(book=book())
    before = Observation(
        book=both,
        quotes=(
            quote(at=both.cash.valuation_at),
            quote(instrument_id="fixture-XAU", at=both.cash.valuation_at),
        ),
    )
    after = Observation(
        book=reduced,
        quotes=(
            quote(at=reduced.cash.valuation_at, bid="100.98", ask="101"),
            quote(instrument_id="fixture-XAU", at=reduced.cash.valuation_at),
        ),
    )
    first, final = project((initial, before)), project((initial, before, after))
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        seq = 0
        for snapshot, kinds in (
            (first, EventType.POSITION_OPENED),
            (final, EventType.POSITION_UPDATED),
        ):
            at = snapshot.source.book.cash.valuation_at
            for position in snapshot.source.book.positions:
                seq += 1
                payload = position_view(snapshot, position.episode_id, T)
                journal.append(
                    event(
                        scope,
                        kinds,
                        seq,
                        occurred_at=at,
                        recorded_at=at,
                        strategy_id=position.strategy_id,
                        symbol=position.asset,
                        payload=payload,
                    )
                )
            for kind, values in (
                (EventType.PORTFOLIO_SNAPSHOT, portfolio_view(snapshot)),
                (EventType.ACCOUNT_SNAPSHOT, account_view(snapshot)),
            ):
                seq += 1
                journal.append(
                    event(scope, kind, seq, occurred_at=at, recorded_at=at, payload=values)
                )
        positions = read_view(conn, "positions", scope.stream_id)["items"]
        assert {p["values"]["symbol"] for p in positions} == {"BTCUSD", "XAUUSD"}
        assert {p["values"]["side"] for p in positions} == {"LONG", "SHORT"}
        assert (
            next(p for p in positions if p["values"]["symbol"] == "BTCUSD")["values"]["quantity"]
            == "0.05"
        )
        portfolio = read_view(conn, "portfolio", scope.stream_id)["items"][0]["values"]
        expected = portfolio_view(final).model_dump(mode="json")
        assert all(portfolio[k] == v for k, v in expected.items())
        assert final.accounting.balance.realized_pnl > 0
        assert final.accounting.unrealized_pnl is not None
        previous = {name: read_view(conn, name, scope.stream_id) for name in TABLES}
        journal.rebuild(scope.stream_id)
        assert {name: read_view(conn, name, scope.stream_id) for name in TABLES} == previous


def test_trade_summary_retained_for_future_utc_calendar(
    server: MonitoringServer, database: Engine, scope: Scope
) -> None:
    closed = event(scope, EventType.POSITION_CLOSED, 2)
    assert isinstance(closed.payload, PositionView)
    summary = {
        "episode_id": closed.payload.episode_id,
        "closed_at": closed.occurred_at,
        "gross_pnl": "5",
        "net_pnl": "4.50",
        "net_r": "0.90",
        "commission": "0.50",
        "financing": "0",
        "spread_cost": None,
        "outcome": "WIN",
        "complete": False,
    }
    closed = closed.model_copy(
        update={"payload": closed.payload.model_copy(update={"trade": summary})}
    )
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        journal.append(event(scope, EventType.POSITION_OPENED))
        journal.append(closed)
        journal.append(closed)
    status, data = http(server, f"/api/v1/trades?stream_id={scope.stream_id}")
    assert status == 200 and len(data["items"]) == 1
    values = data["items"][0]["values"]
    assert values["net_pnl"] == "4.50" and values["net_r"] == "0.90"
    assert values["spread_cost"] is None and values["outcome"] == "WIN"


@pytest.mark.parametrize(
    "component",
    [
        "database",
        "broker",
        "market_data",
        "risk_engine",
        "portfolio",
        "strategy",
        "ea",
        "reconciliation",
    ],
)
def test_all_health_components_are_observations(
    database: Engine, scope: Scope, component: str
) -> None:
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        for seq, state in enumerate(("HEALTHY", "DEGRADED", "STALE", "DISCONNECTED", "ERROR"), 1):
            payload = HealthView.model_validate({"component": component, "state": state})
            journal.append(event(scope, seq=seq, payload=payload))
            values = read_view(conn, "system", scope.stream_id)["items"][0]["values"]
            assert values["component"] == component and values["state"] == state
            assert read_view(conn, "risk", scope.stream_id)["items"] == []


def test_wrong_entity_correction_and_closed_reopen_rejected(database: Engine, scope: Scope) -> None:
    original = event(scope, EventType.POSITION_OPENED)
    assert isinstance(original.payload, PositionView)
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        journal.append(original)
        with pytest.raises(ValueError, match="CORRECTION_POSITION"):
            journal.append(
                event(
                    scope,
                    EventType.POSITION_OPENED,
                    2,
                    corrects_event_id=original.event_id,
                    payload=original.payload.model_copy(
                        update={"episode_id": uuid4(), "updated_at": T + timedelta(seconds=2)}
                    ),
                )
            )
        journal.append(event(scope, EventType.POSITION_CLOSED, 2))
        with pytest.raises(ValueError, match="CANNOT_REOPEN"):
            journal.append(event(scope, EventType.POSITION_UPDATED, 3))
        assert len(journal.replay(scope.stream_id)) == 2


def test_api_reports_corruption_without_leaking_sql(
    server: MonitoringServer, database: Engine, scope: Scope
) -> None:
    with database.begin() as conn:
        TelemetryJournal(conn).append(event(scope))
        conn.execute(
            update(schema.system_health_projection)
            .where(schema.system_health_projection.c.stream_id == scope.stream_id)
            .values(body={})
        )
    assert http(server, f"/api/v1/system?stream_id={scope.stream_id}") == (
        503,
        {"error": "MONITORING_DATA_UNAVAILABLE"},
    )


def test_concurrent_retry_serializes_once(database: Engine, scope: Scope) -> None:
    e = event(scope, EventType.PORTFOLIO_SNAPSHOT)

    def publish(_: int) -> str:
        with database.begin() as conn:
            return TelemetryJournal(conn).append(e).event_hash

    with ThreadPoolExecutor(max_workers=2) as pool:
        hashes = list(pool.map(publish, range(2)))
    assert hashes[0] == hashes[1]
    with database.connect() as conn:
        assert len(TelemetryJournal(conn).replay(scope.stream_id)) == 1


def test_api_health_loopback(server: MonitoringServer) -> None:
    assert server.server_address[0] == "127.0.0.1"
    assert http(server, "/health") == (
        200,
        {"status": "HEALTHY", "database": "HEALTHY", "read_only": True},
    )


@pytest.mark.parametrize(
    "name,kind",
    [
        ("account", EventType.ACCOUNT_SNAPSHOT),
        ("portfolio", EventType.PORTFOLIO_SNAPSHOT),
        ("positions", EventType.POSITION_OPENED),
        ("risk", EventType.RISK_APPROVED),
        ("system", EventType.BROKER_CONNECTED),
        ("activity", EventType.EA_STARTED),
        ("events", EventType.SYSTEM_STARTED),
    ],
)
def test_api_committed_read_models(
    server: MonitoringServer, database: Engine, scope: Scope, name: str, kind: EventType
) -> None:
    with database.begin() as conn:
        TelemetryJournal(conn).append(event(scope, kind))
    status, data = http(server, f"/api/v1/{name}?stream_id={scope.stream_id}")
    assert status == 200 and data["read_only"] is True and len(data["items"]) == 1
    assert data["next_cursor"] == 1


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "?stream_id=bad",
        "?stream_id={s}&limit=0",
        "?stream_id={s}&limit=1001",
        "?stream_id={s}&after=-1",
        "?stream_id={s}&unknown=1",
        "?stream_id={s}&after=0&after=1",
        "?stream_id={s}&follow=true",
    ],
)
def test_api_invalid_queries(server: MonitoringServer, scope: Scope, suffix: str) -> None:
    assert http(server, "/api/v1/events" + suffix.format(s=scope.stream_id))[0] == 400


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_api_is_read_only(server: MonitoringServer, method: str) -> None:
    assert http(server, "/api/v1/positions", method)[0] == 405


@pytest.mark.parametrize(
    "headers", [{"Origin": "https://example.invalid"}, {"Host": "example.invalid"}]
)
def test_api_rejects_remote_browser_origin(
    server: MonitoringServer, headers: dict[str, str]
) -> None:
    assert http(server, "/health", headers=headers)[0] == 403


def test_api_unknown_path(server: MonitoringServer) -> None:
    assert http(server, "/api/v1/order_send")[0] == 404


def test_sse_reconnect_duplicate_suppression(
    server: MonitoringServer, database: Engine, scope: Scope
) -> None:
    with database.begin() as conn:
        journal = TelemetryJournal(conn)
        for seq in range(1, 4):
            journal.append(event(scope, seq=seq))
        journal.append(event(scope, seq=2))
    path = f"/api/v1/stream?stream_id={scope.stream_id}&follow=false"
    status, body = http(server, path + "&limit=2")
    assert status == 200 and body.count("\nid:") == 1
    assert body.startswith("id: 1\n") and "id: 2\n" in body and "id: 3\n" not in body
    _, body = http(server, path, headers={"Last-Event-ID": "2"})
    assert body.startswith("id: 3\n") and body.count("data:") == 1
    assert http(server, path, headers={"Last-Event-ID": "3"})[1] == ": heartbeat\n\n"


def frame(response: HTTPResponse) -> str:
    lines = []
    while line := response.readline():
        if line == b"\n":
            break
        lines.append(line.decode())
    return "".join(lines)


def test_sse_publish_after_connect_and_rollback_invisible(
    server: MonitoringServer, database: Engine, scope: Scope
) -> None:
    with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as client:
        client.request("GET", f"/api/v1/stream?stream_id={scope.stream_id}")
        response = client.getresponse()
        assert response.status == 200 and frame(response).startswith(": heartbeat")
        with database.connect() as conn:
            TelemetryJournal(conn).append(event(scope))
            conn.rollback()
        with database.connect() as conn:
            assert read_events(conn, scope.stream_id) == ()
        with database.begin() as conn:
            TelemetryJournal(conn).append(event(scope))
        for _ in range(5):
            received = frame(response)
            if received.startswith("id:"):
                break
        assert received.startswith("id: 1\n")
        with database.begin() as conn:
            TelemetryJournal(conn).append(event(scope, seq=2))
        for _ in range(5):
            received = frame(response)
            if received.startswith("id:"):
                break
        assert received.startswith("id: 2\n")
