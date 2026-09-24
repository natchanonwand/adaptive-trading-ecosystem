"""Instrument the unchanged observer with fake inputs, outside its production path."""

import hashlib
import json
import os
import statistics
import time
import tracemalloc
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, event, func, select

from tests.observer.fixtures import SYMBOLS, FakeObserver, T, position, trade
from trading_ecosystem.observer.export import export_session
from trading_ecosystem.observer.runtime import Observer
from trading_ecosystem.observer.store import events, install


def distribution(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return dict(
        min=ordered[0],
        median=statistics.median(ordered),
        p95=ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.95 + 0.5))],
        max=ordered[-1],
    )


def run(root: Path, stress: bool, traced: bool) -> dict[str, Any]:
    total_start = time.perf_counter()
    engine = create_engine(os.environ["TE_DATABASE_URL"])
    install(engine)
    client = FakeObserver()
    base = client.observation_session()
    candidates = (
        tuple(
            base.config.candidates[0].model_copy(
                update={
                    "ea_id": f"fixture-{i}",
                    "magic_numbers": (100 + i,),
                }
            )
            for i in range(3)
        )
        if stress
        else base.config.candidates
    )
    session = base.model_copy(
        update={
            "session_id": uuid4(),
            "config": base.config.model_copy(update={"candidates": candidates}),
        }
    )
    observer = Observer(client, engine, session)
    setup = time.perf_counter() - total_start
    commits: list[float] = []
    queries: list[float] = []
    query_start = [0.0]

    def before(*args: Any) -> None:
        query_start[0] = time.perf_counter()

    def after(*args: Any) -> None:
        queries.append((time.perf_counter() - query_start[0]) * 1000)

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    original_commit = engine.dialect.do_commit

    def commit(connection: Any) -> None:
        began = time.perf_counter()
        original_commit(connection)
        commits.append((time.perf_counter() - began) * 1000)

    processing, mutation, sleeping, event_counts, commit_per_poll, query_per_poll = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    prior_count = 0
    if traced:
        tracemalloc.start()
    loop_start = time.perf_counter()
    cpu_start = time.process_time()
    with patch.object(engine.dialect, "do_commit", commit):
        for tick in range(12 if stress else 60):
            began = time.perf_counter()
            client.now = T + timedelta(seconds=tick)
            if stress:
                client.positions = tuple(
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
                    client.deals = tuple(
                        trade(
                            1000 + i,
                            0,
                            position_id=1000 + i,
                            symbol=SYMBOLS[i % 3],
                            magic=100 + i % 3,
                        )
                        for i in range(12)
                    )
            elif tick == 2:
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
                    trade(
                        6, tick, position_id=200, symbol="XAUUSDm", entry=2, type=1, volume=".20"
                    ),
                )
            elif tick == 50:
                client.positions = ()
                client.deals += (
                    trade(7, tick, position_id=200, symbol="XAUUSDm", entry=1, type=0),
                )
            mutation.append((time.perf_counter() - began) * 1000)
            commits.clear()
            queries.clear()
            began = time.perf_counter()
            if not observer.step(client.now):
                raise RuntimeError("QUALIFICATION_POLL_FAILED")
            processing.append((time.perf_counter() - began) * 1000)
            commit_per_poll.append(sum(commits))
            query_per_poll.append(sum(queries))
            with engine.connect() as conn:
                count = conn.execute(
                    select(func.count())
                    .select_from(events)
                    .where(events.c.session_id == session.session_id)
                ).scalar_one()
            event_counts.append(count - prior_count)
            prior_count = count
            began = time.perf_counter()
            if not stress:
                time.sleep(max(0, (1000 - processing[-1] - mutation[-1]) / 1000))
            sleeping.append((time.perf_counter() - began) * 1000)
    loop_seconds = time.perf_counter() - loop_start
    cpu = time.process_time() - cpu_start
    peak = tracemalloc.get_traced_memory()[1] if traced else None
    if traced:
        tracemalloc.stop()
    began = time.perf_counter()
    observer.stop(client.now)
    teardown = time.perf_counter() - began
    began = time.perf_counter()
    with engine.connect() as conn:
        export_session(conn, session, root / "export")
    export_seconds = time.perf_counter() - began
    engine.dispose()
    return dict(
        session_id=str(session.session_id),
        traced_python_memory=traced,
        requested_poll_interval_ms=1000,
        scheduled_sleep=not stress,
        poll_processing_ms=distribution(processing),
        poll_samples_ms=processing,
        missed_deadline_count=sum(v > 1000 for v in processing),
        database_commit_ms=distribution(commit_per_poll),
        database_statement_ms=distribution(query_per_poll),
        events_generated_per_poll=event_counts,
        fixture_mutation_ms=sum(mutation),
        sleep_seconds=sum(sleeping) / 1000,
        setup_seconds=setup,
        teardown_seconds=teardown,
        export_seconds=export_seconds,
        loop_seconds=loop_seconds,
        cpu_seconds=cpu,
        total_wall_seconds=time.perf_counter() - total_start,
        python_peak_bytes=peak,
    )


def main() -> None:
    root = Path(".local/phase4_c")
    root.mkdir(exist_ok=True)
    baseline = root / "preserved-evidence.json"
    if baseline.exists():
        raise ValueError("PRESERVE_EXISTING_QUALIFICATION")
    paths = [
        p
        for folder in ("data/datasets", "data/research", ".local/phase4_b")
        for p in Path(folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    baseline.write_text(
        json.dumps(
            {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2
        ),
        encoding="utf-8",
    )
    results = {}
    for name, stress, traced in (
        ("normal", False, False),
        ("stress", True, False),
        ("stress-traced", True, True),
    ):
        directory = root / ("polling-" + name)
        directory.mkdir()
        results[name] = run(directory, stress, traced)
        (directory / "timing.json").write_text(
            json.dumps(results[name], indent=2), encoding="utf-8"
        )
    (root / "polling.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("PASS: unchanged observer instrumented; timing evidence retained")


if __name__ == "__main__":
    main()
