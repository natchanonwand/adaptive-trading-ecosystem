from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from threading import Thread

import pytest
from sqlalchemy import Engine, delete, select, update

from tests.integration.test_monitoring import http
from tests.integration.test_monitoring import monitoring_migration as monitoring_migration
from tests.mt5.fake import FakeClient, T, deal, position
from trading_ecosystem.dashboard_api.server import DashboardServer
from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.monitoring import schema
from trading_ecosystem.monitoring.journal import TelemetryJournal
from trading_ecosystem.monitoring.queries import read_view
from trading_ecosystem.mt5.bridge import Bridge, ConnectionState
from trading_ecosystem.mt5.config import BridgeConfig
from trading_ecosystem.mt5.store import checkpoints, install, observations


@pytest.fixture
def bridge(database: Engine) -> Bridge:
    install(database)
    return Bridge(
        FakeClient(),
        database,
        BridgeConfig(
            aliases={"XAUUSD": "TEST.b"}, history_window_seconds=86400, initial_history_days=1
        ),
    )


def client(bridge: Bridge) -> FakeClient:
    assert isinstance(bridge.client, FakeClient)
    return bridge.client


def events(bridge: Bridge) -> int:
    with bridge.engine.begin() as conn:
        return len(TelemetryJournal(conn).replay(bridge.scope.stream_id))


def checkpoint(bridge: Bridge) -> dict[str, object]:
    with bridge.engine.connect() as conn:
        value = conn.execute(
            select(checkpoints.c.body).where(checkpoints.c.scope_id == bridge.scope.stream_id)
        ).scalar_one()
        assert isinstance(value, dict)
        return value


@pytest.fixture
def api(database: Engine) -> Iterator[DashboardServer]:
    with DashboardServer(database, 0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(5)


def test_fake_to_journal_api_sse_and_unknown_account_values(
    bridge: Bridge, api: DashboardServer
) -> None:
    assert bridge.step(T)
    url = f"/api/v1/dashboard/snapshot?stream_id={bridge.scope.stream_id}"
    status, data = http(api, url)
    assert status == 200 and data["scope"]["environment"] == "DEMO"
    values = data["views"]["account"]["items"][0]["values"]
    assert Decimal(values["balance"]) == Decimal("10000") and values["realized_pnl"] is None
    positions = data["views"]["positions"]["items"]
    assert len(positions) == 1 and positions[0]["values"]["magic_number"] == 77
    assert positions[0]["values"]["broker_ticket"] == "1"
    status, frames = http(api, f"/api/v1/stream?stream_id={bridge.scope.stream_id}&follow=false")
    assert status == 200 and "event: ACCOUNT_SNAPSHOT" in frames


def test_unchanged_poll_does_not_emit_storm(bridge: Bridge) -> None:
    assert bridge.step(T)
    count = events(bridge)
    for seconds in range(1, 5):
        assert bridge.step(T + timedelta(seconds=seconds))
    assert events(bridge) == count
    assert bridge.step(T + timedelta(seconds=5))
    assert events(bridge) == count + 4  # broker/account/quote/database freshness heartbeat


def test_restart_same_timestamp_duplicate_and_late_history(bridge: Bridge) -> None:
    fake = client(bridge)
    fake.deals = (deal(1), deal(2), deal(1))
    assert bridge.step(T)
    with bridge.engine.connect() as conn:
        records = conn.execute(
            select(observations).where(
                observations.c.scope_id == bridge.scope.stream_id, observations.c.kind == "DEAL"
            )
        ).all()
        assert len(records) == 2
    restart = Bridge(fake, bridge.engine, bridge.config)
    late = {
        **deal(3),
        "time": int(T.timestamp()) - 20,
        "time_msc": int(T.timestamp()) * 1000 - 20000,
    }
    fake.deals = (*fake.deals, late)
    assert restart.step(T + timedelta(seconds=10))
    assert fake.windows[-1][0] == T - timedelta(seconds=120)
    with bridge.engine.connect() as conn:
        records = conn.execute(
            select(observations).where(
                observations.c.scope_id == bridge.scope.stream_id, observations.c.kind == "DEAL"
            )
        ).all()
        assert len(records) == 3
    assert checkpoint(restart)["deal_watermark"] == [
        int(T.timestamp()) - 1,
        int(T.timestamp()) * 1000 - 1000,
        2,
    ]


def test_history_error_does_not_advance_checkpoint_or_close_positions(bridge: Bridge) -> None:
    assert bridge.step(T)
    before = checkpoint(bridge)
    client(bridge).fail = "deals"
    assert not bridge.step(T + timedelta(seconds=10))
    after = checkpoint(bridge)
    assert after["history_until"] == before["history_until"]
    assert after["positions"] == before["positions"]
    with bridge.engine.connect() as conn:
        account = read_view(conn, "account", bridge.scope.stream_id)["items"][0]["values"]
        assert account["stale"] is True


def test_conflicting_duplicate_fails_without_new_deal_or_pnl(bridge: Bridge) -> None:
    assert bridge.step(T)
    before = checkpoint(bridge)
    client(bridge).deals = ({**deal(), "profit": 1000.0},)
    assert not bridge.step(T + timedelta(seconds=10))
    assert checkpoint(bridge)["history_until"] == before["history_until"]
    with bridge.engine.connect() as conn:
        records = conn.execute(
            select(observations).where(
                observations.c.scope_id == bridge.scope.stream_id, observations.c.kind == "DEAL"
            )
        ).all()
        assert len(records) == 1


@pytest.mark.parametrize(
    "method",
    [
        "initialize",
        "terminal",
        "account",
        "symbols",
        "positions",
        "orders",
        "tick",
        "deals",
        "history_orders",
    ],
)
def test_api_failure_backoff_and_reconnect(bridge: Bridge, method: str) -> None:
    fake = client(bridge)
    fake.fail = method
    assert not bridge.step(T)
    attempts = fake.initializes
    assert not bridge.step(T + timedelta(seconds=1))
    assert fake.initializes == attempts and fake.shutdowns == 1
    fake.fail = None
    assert bridge.step(T + timedelta(seconds=2))
    assert bridge.state == ConnectionState.CONNECTED


@pytest.mark.parametrize("mode", [1, 2, None, False])
def test_non_demo_refused_without_financial_observation(bridge: Bridge, mode: object) -> None:
    client(bridge).account["trade_mode"] = mode
    assert not bridge.step(T) and bridge.refused
    with bridge.engine.connect() as conn:
        assert not read_view(conn, "account", bridge.scope.stream_id)["items"]


def test_empty_positions_are_valid_none_error_does_not_mean_closed(bridge: Bridge) -> None:
    assert bridge.step(T)
    fake = client(bridge)
    fake.fail = "positions"
    assert not bridge.step(T + timedelta(seconds=1))
    assert checkpoint(bridge)["positions"]
    fake.fail, fake.positions = None, ()
    assert bridge.step(T + timedelta(seconds=3))
    assert checkpoint(bridge)["positions"] == {}
    with bridge.engine.connect() as conn:
        trades = read_view(conn, "trades", bridge.scope.stream_id)["items"]
        assert trades[0]["values"]["net_pnl"] is None


@pytest.mark.parametrize("corrupt", [False, True])
def test_projection_missing_or_changed_resyncs_from_journal(bridge: Bridge, corrupt: bool) -> None:
    assert bridge.step(T)
    with bridge.engine.begin() as conn:
        target = schema.position_projection
        if corrupt:
            row = (
                conn.execute(select(target).where(target.c.stream_id == bridge.scope.stream_id))
                .mappings()
                .one()
            )
            body = {**row["body"], "quantity": "99"}
            conn.execute(
                update(target)
                .where(target.c.stream_id == bridge.scope.stream_id)
                .values(body=body, body_hash=digest(canonical_bytes(body)))
            )
        else:
            conn.execute(delete(target).where(target.c.stream_id == bridge.scope.stream_id))
    assert bridge.step(T + timedelta(seconds=1))
    with bridge.engine.connect() as conn:
        rows = read_view(conn, "positions", bridge.scope.stream_id)["items"]
        assert rows[0]["values"]["quantity"] == "0.1"


def test_external_positions_new_multiple_and_reversal(bridge: Bridge) -> None:
    fake = client(bridge)
    fake.positions = (position(1), {**position(2, 1), "symbol": "OTHER.b"})
    assert bridge.step(T)
    fake.positions = (position(1, 1),)
    assert bridge.step(T + timedelta(seconds=1))
    with bridge.engine.connect() as conn:
        rows = read_view(conn, "positions", bridge.scope.stream_id)["items"]
        assert len(rows) == 3
        assert sum(row["values"]["state"] == "OPEN" for row in rows) == 1


def test_quote_stale_and_graceful_stop(bridge: Bridge) -> None:
    assert bridge.step(T + timedelta(seconds=60))
    assert bridge.state == ConnectionState.STALE
    bridge.stop(T + timedelta(seconds=61))
    assert client(bridge).shutdowns == 1 and bridge.state.value == "DISCONNECTED"


def test_account_switch_reconnect_does_not_mix_streams(bridge: Bridge) -> None:
    assert bridge.step(T)
    original = bridge.scope.stream_id
    client(bridge).account["login"] += 1
    assert not bridge.step(T + timedelta(seconds=1))
    assert bridge.scope.stream_id == original
    assert bridge.step(T + timedelta(seconds=3))
    assert bridge.scope.stream_id != original


def test_pending_orders_remain_distinct_from_positions(bridge: Bridge) -> None:
    fake = client(bridge)
    fake.positions = ()
    fake.orders = (
        {
            "ticket": 7,
            "position_id": 0,
            "type": 2,
            "magic": 77,
            "comment": "pending fixture",
            "symbol": "TEST.b",
            "volume_current": 0.3,
            "price_open": 1900.0,
            "sl": 1800.0,
            "tp": 2100.0,
        },
    )
    assert bridge.step(T)
    saved = checkpoint(bridge)
    orders = saved["orders"]
    assert saved["positions"] == {} and isinstance(orders, dict) and len(orders) == 1
    with bridge.engine.connect() as conn:
        assert read_view(conn, "positions", bridge.scope.stream_id)["items"] == []
        portfolio = read_view(conn, "portfolio", bridge.scope.stream_id)["items"][0]["values"]
        assert portfolio["open_positions"] == 0 and portfolio["reserved_positions"] is None


def test_history_limit_preserves_atomic_state(bridge: Bridge) -> None:
    bridge.config = bridge.config.model_copy(update={"max_history_records": 1})
    client(bridge).deals = (deal(1), deal(2))
    assert not bridge.step(T)
    assert checkpoint(bridge).get("history_until") is None
    with bridge.engine.connect() as conn:
        assert read_view(conn, "account", bridge.scope.stream_id)["items"] == []


def test_explicit_alias_mismatch_never_fuzzy_maps(bridge: Bridge) -> None:
    bridge.config = bridge.config.model_copy(update={"aliases": {"XAUUSD": "TEST"}})
    assert not bridge.step(T)
    with bridge.engine.connect() as conn:
        assert read_view(conn, "positions", bridge.scope.stream_id)["items"] == []
