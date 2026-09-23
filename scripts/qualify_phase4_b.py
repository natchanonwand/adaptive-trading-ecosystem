"""Explicit deterministic fake EA qualification; never attaches to MT5 or creates trades."""

import hashlib
import json
import os
import time
import tracemalloc
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, func, select, text

from tests.observer.fixtures import SYMBOLS, FakeObserver, T, position, trade
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.observer.export import export_session, verify_export
from trading_ecosystem.observer.runtime import Observer
from trading_ecosystem.observer.store import events, install, load_frames


def main() -> None:
    root = Path(".local/phase4_b/final")
    root.mkdir(parents=True, exist_ok=True)
    result_path = root / "qualification.json"
    if result_path.exists():
        raise ValueError("QUALIFICATION_EVIDENCE_ALREADY_EXISTS")
    engine = create_engine(os.environ["TE_DATABASE_URL"])
    install(engine)
    client = FakeObserver()
    session = client.observation_session().model_copy(update={"session_id": uuid4()})
    observer = Observer(client, engine, session)
    with engine.connect() as conn:
        size_before = conn.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
    tracemalloc.start()
    wall, cpu = time.perf_counter(), time.process_time()
    latencies = []
    for tick in range(60):
        began = time.perf_counter()
        client.now = T + timedelta(seconds=tick)
        if tick == 2:
            client.positions = (position(),)
            client.deals += (trade(1, tick),)
        elif tick == 8:
            client.positions = ({**position(), "volume": ".20"},)
            client.deals += (trade(2, tick),)
        elif tick == 14:
            client.positions = ({**position(), "volume": ".15"},)
            client.deals += (trade(3, tick, entry=1, type=1, volume=".05", profit=".05"),)
        elif tick == 20:
            client.positions = ({**client.positions[0], "sl": "96"},)
        elif tick == 26:
            client.positions = ({**client.positions[0], "tp": "0"},)
        elif tick == 30:
            observer = Observer(client, engine, session)
        elif tick == 32:
            client.positions = ()
            client.deals += (trade(4, tick, entry=1, type=1, volume=".15", profit=".30"),)
        elif tick == 38:
            client.positions = (
                {**position(), "identifier": 200, "ticket": 200, "symbol": "XAUUSDm"},
            )
            client.deals += (trade(5, tick, position_id=200, symbol="XAUUSDm"),)
        elif tick == 45:
            client.positions = ({**client.positions[0], "type": 1},)
            client.deals += (
                trade(6, tick, position_id=200, symbol="XAUUSDm", entry=2, type=1, volume=".20"),
            )
        elif tick == 50:
            client.positions = ()
            client.deals += (trade(7, tick, position_id=200, symbol="XAUUSDm", entry=1, type=0),)
        if not observer.step(client.now):
            raise ValueError("FAKE_QUALIFICATION_POLL_FAILED")
        latencies.append(time.perf_counter() - began)
        time.sleep(max(0.001, 1 - latencies[-1]))
    observer.stop(T + timedelta(seconds=60))
    elapsed = time.perf_counter() - wall
    normal_cpu = time.process_time() - cpu
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    with engine.connect() as conn:
        size_after = conn.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
        event_count = conn.execute(
            select(func.count())
            .select_from(events)
            .where(events.c.session_id == session.session_id)
        ).scalar_one()
        raw_count = len(load_frames(conn, session))
        export_session(conn, session, root / "normal-export")
        export_session(conn, session, root / "normal-repeat-export")
    if (root / "normal-export/manifest.json").read_bytes() != (
        root / "normal-repeat-export/manifest.json"
    ).read_bytes():
        raise ValueError("NONDETERMINISTIC_EXPORT")
    stress_client = FakeObserver()
    base = stress_client.observation_session()
    candidate = base.config.candidates[0]
    candidates = tuple(
        candidate.model_copy(
            update={
                "ea_id": f"fixture-{i}",
                "display_name": f"Fixture EA {i}",
                "magic_numbers": (100 + i,),
            }
        )
        for i in range(3)
    )
    stress_session = base.model_copy(
        update={
            "session_id": uuid4(),
            "config": base.config.model_copy(update={"candidates": candidates}),
        }
    )
    stress = Observer(stress_client, engine, stress_session)
    with engine.connect() as conn:
        stress_size_before = conn.execute(
            text("SELECT pg_database_size(current_database())")
        ).scalar_one()
    tracemalloc.start()
    stress_wall, stress_cpu = time.perf_counter(), time.process_time()
    for tick in range(12):
        stress_client.now = T + timedelta(seconds=tick)
        stress_client.positions = tuple(
            {
                **position(),
                "identifier": 1000 + i,
                "ticket": 1000 + i,
                "symbol": SYMBOLS[i % 3],
                "magic": 100 + i % 3,
                "sl": str(90 + tick / 10),
            }
            for i in range(12)
        )
        if tick == 0:
            stress_client.deals = tuple(
                trade(1000 + i, 0, position_id=1000 + i, symbol=SYMBOLS[i % 3], magic=100 + i % 3)
                for i in range(12)
            )
        if not stress.step(stress_client.now):
            raise ValueError("FAKE_STRESS_POLL_FAILED")
    stress.stop(T + timedelta(seconds=12))
    stress_elapsed = time.perf_counter() - stress_wall
    stress_cpu_elapsed = time.process_time() - stress_cpu
    stress_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    with engine.connect() as conn:
        stress_size_after = conn.execute(
            text("SELECT pg_database_size(current_database())")
        ).scalar_one()
        stress_raw_count = len(load_frames(conn, stress_session))
        stress_manifest = export_session(conn, stress_session, root / "stress-export")
    result: Record = {
        "provenance": "DETERMINISTIC_FAKE_NOT_REAL_EXTERNAL_EA",
        "real_external_ea_smoke": "BLOCKED_NOT_PROVIDED",
        "normal_session": str(session.session_id),
        "stress_session": str(stress_session.session_id),
        "normal": {
            "ea_candidates": 1,
            "symbols": 3,
            "poll_interval_seconds": 1,
            "polls": 60,
            "wall_seconds": elapsed,
            "cpu_seconds": normal_cpu,
            "cpu_one_core_percent": normal_cpu / elapsed * 100,
            "python_peak_bytes": peak,
            "max_poll_seconds": max(latencies),
            "database_growth_bytes": size_after - size_before,
            "events": event_count,
            "raw_observation_count": raw_count,
            "errors": 0,
            "events_per_hour_extrapolated": event_count / elapsed * 3600,
        },
        "stress": {
            "ea_candidates": 3,
            "positions": 12,
            "rapid_modification_polls": 12,
            "polls": 12,
            "wall_seconds": stress_elapsed,
            "cpu_seconds": stress_cpu_elapsed,
            "cpu_one_core_percent": stress_cpu_elapsed / stress_elapsed * 100,
            "python_peak_bytes": stress_peak,
            "database_growth_bytes": stress_size_after - stress_size_before,
            "raw_observation_count": stress_raw_count,
            "errors": 0,
            "events": stress_manifest["datasets"]["external_ea_events"]["rows"],
        },
        "exports": {},
    }
    for name in ("normal-export", "normal-repeat-export", "stress-export"):
        verify_export(root / name)
        result["exports"][name] = hashlib.sha256(
            (root / name / "manifest.json").read_bytes()
        ).hexdigest()
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    engine.dispose()
    print("PASS: fake 60-second observer benchmark, restart, stress and deterministic exports")


if __name__ == "__main__":
    main()
