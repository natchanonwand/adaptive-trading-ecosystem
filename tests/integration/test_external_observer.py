from datetime import timedelta
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
from sqlalchemy import Engine, select, update

from tests.integration.test_monitoring import http
from tests.integration.test_monitoring import monitoring_migration as monitoring_migration
from tests.observer.fixtures import FakeObserver, T, position, trade
from trading_ecosystem.mt5.store import observations
from trading_ecosystem.observer.api import ObserverServer
from trading_ecosystem.observer.export import export_session, verify_export
from trading_ecosystem.observer.runtime import Observer
from trading_ecosystem.observer.store import events, install, load_frames, scope


@pytest.fixture
def observer(database: Engine) -> Observer:
    install(database)
    client = FakeObserver()
    session = client.observation_session().model_copy(update={"session_id": uuid4()})
    return Observer(client, database, session)


def fake(observer: Observer) -> FakeObserver:
    assert isinstance(observer.client, FakeObserver)
    return observer.client


def advance(observer: Observer, seconds: int) -> bool:
    fake(observer).now = T + timedelta(seconds=seconds)
    return observer.step(fake(observer).now)


def test_restart_recovered_modification_partial_close_and_overlap(observer: Observer) -> None:
    client = fake(observer)
    assert advance(observer, 0)
    client.positions = (position(),)
    client.deals = (trade(1, 1),)
    assert advance(observer, 3)
    restarted = Observer(client, observer.engine, observer.session)
    client.positions = ({**position(), "volume": ".05", "sl": "96"},)
    client.deals += (trade(2, 4, type=1, entry=1, volume=".05"),)
    assert advance(restarted, 6)
    with observer.engine.connect() as conn:
        before = list(
            conn.execute(
                select(events.c.body).where(events.c.session_id == observer.session.session_id)
            ).scalars()
        )
        assert any(e["kind"] == "POSITION_REDUCED" and e["recovered_state"] for e in before)
        assert any(e["kind"] == "STOP_LOSS_CHANGED" and e["recovered_state"] for e in before)
    assert advance(restarted, 9)
    with observer.engine.connect() as conn:
        after = list(
            conn.execute(
                select(events.c.body).where(events.c.session_id == observer.session.session_id)
            ).scalars()
        )
    assert before == after


def test_deterministic_parquet_export_replay_and_hash_tampering(
    observer: Observer, tmp_path: Path
) -> None:
    client = fake(observer)
    client.positions = (position(),)
    client.deals = (trade(1, 0),)
    assert advance(observer, 0)
    client.positions = ()
    client.deals += (trade(2, 3, type=1, entry=1, profit="1"),)
    assert advance(observer, 3)
    with observer.engine.connect() as conn:
        one = export_session(conn, observer.session, tmp_path / "one")
        two = export_session(conn, observer.session, tmp_path / "two")
    assert one == two
    assert verify_export(tmp_path / "one") == one
    for name in one["datasets"]:
        assert (tmp_path / "one" / (name + ".parquet")).read_bytes() == (
            tmp_path / "two" / (name + ".parquet")
        ).read_bytes()
    with (tmp_path / "one" / "external_ea_events.parquet").open("ab") as out:
        out.write(b"tamper")
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        verify_export(tmp_path / "one")


@pytest.mark.parametrize("field,value", [("trade_mode", 2), ("margin_mode", 0), ("login", 1)])
def test_demo_identity_and_position_mode_fail_closed(
    observer: Observer, field: str, value: int
) -> None:
    fake(observer).account[field] = value
    assert not advance(observer, 0)
    with observer.engine.connect() as conn:
        assert not load_frames(conn, observer.session)


def test_floating_price_changes_do_not_create_behavior_storm(observer: Observer) -> None:
    client = fake(observer)
    client.positions = (position(),)
    assert advance(observer, 0)
    for second in range(1, 6):
        client.positions = (
            {**position(), "profit": str(second), "price_current": str(100 + second)},
        )
        assert advance(observer, second)
    assert observer.new_frames == 1


def test_raw_corruption_rejected_on_restart(observer: Observer) -> None:
    assert advance(observer, 0)
    with observer.engine.begin() as conn:
        conn.execute(
            update(observations)
            .where(
                observations.c.scope_id == scope(observer.session).stream_id,
                observations.c.kind == "EA_FRAME",
            )
            .values(body={"bad": True})
        )
    with pytest.raises(ValueError, match="INTEGRITY"):
        Observer(fake(observer), observer.engine, observer.session)


def test_canceled_order_during_gap_retained_without_fabricated_fill(observer: Observer) -> None:
    assert advance(observer, 0)
    client = fake(observer)
    client.history_orders = (
        {
            "ticket": 999,
            "symbol": "BTCUSDm",
            "magic": 77,
            "comment": "fixture",
            "state": 2,
            "volume_initial": ".1",
        },
    )
    restarted = Observer(client, observer.engine, observer.session)
    assert advance(restarted, 6)
    with observer.engine.connect() as conn:
        retained = load_frames(conn, observer.session)
        assert retained[-1].history_orders[0]["ticket"] == 999
        rows = list(
            conn.execute(
                select(events.c.body).where(events.c.session_id == observer.session.session_id)
            ).scalars()
        )
        assert any(e["kind"] == "ORDER_HISTORY_OBSERVED" and e["recovered_state"] for e in rows)
        assert not any(e["kind"] == "POSITION_OPENED" for e in rows)
    assert advance(restarted, 9)
    assert restarted.new_frames == 1


def test_observer_api_local_get_only_and_unknown_metrics(observer: Observer) -> None:
    assert advance(observer, 0)
    with ObserverServer(observer.engine, 0) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            status, data = http(
                server, f"/api/v1/observer?session_id={observer.session.session_id}"
            )
            assert status == 200 and data["selected"]["read_only"]
            assert data["selected"]["summary"]["gross_pnl"] is None
            assert http(server, "/api/v1/observer?unknown=1")[0] == 400
            assert http(server, "/api/v1/observer", method="POST")[0] == 405
            assert (
                http(server, "/api/v1/observer", headers={"Origin": "https://example.com"})[0]
                == 403
            )
        finally:
            server.shutdown()
            worker.join(5)


def test_history_error_does_not_fabricate_close(
    observer: Observer, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = fake(observer)
    client.positions = (position(),)
    assert advance(observer, 0)
    client.positions = ()

    def unavailable(*args: object) -> tuple[dict[str, object], ...]:
        raise RuntimeError("HISTORY_UNAVAILABLE")

    with monkeypatch.context() as patch:
        patch.setattr(client, "history_deals_get", unavailable)
        assert not advance(observer, 3)
    assert advance(observer, 6)
    with observer.engine.connect() as conn:
        rows = list(
            conn.execute(
                select(events.c.body).where(events.c.session_id == observer.session.session_id)
            ).scalars()
        )
    missing = next(e for e in rows if e["kind"] == "POSITION_REMOVED_OBSERVED")
    assert missing["recovered_state"]
    assert not any(e["kind"] == "POSITION_CLOSED" for e in rows)


def test_context_windows_deduplicated_across_close_polls(observer: Observer) -> None:
    client = fake(observer)
    client.positions = (position(),)
    assert advance(observer, 1)
    client.positions = ({**position(), "sl": "96"},)
    assert advance(observer, 2)
    with observer.engine.connect() as conn:
        frames = load_frames(conn, observer.session)
    first = {ref["window_id"] for c in frames[0].contexts.values() for ref in c["windows"].values()}
    second = {
        ref["window_id"] for c in frames[1].contexts.values() for ref in c["windows"].values()
    }
    assert first == second
