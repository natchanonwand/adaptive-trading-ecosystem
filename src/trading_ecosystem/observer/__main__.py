"""Run a bounded DEMO-only observer session; no EA installation or activation."""

import argparse
import json
import os
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread
from uuid import UUID, uuid4

from sqlalchemy import create_engine

from trading_ecosystem.mt5.calibration import require_demo
from trading_ecosystem.mt5.normalization import account_identity
from trading_ecosystem.observer.api import ObserverServer
from trading_ecosystem.observer.contracts import Config, ObservationSession
from trading_ecosystem.observer.export import export_session
from trading_ecosystem.observer.native import NativeObserverClient
from trading_ecosystem.observer.runtime import Observer
from trading_ecosystem.observer.store import get_session, install


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--resume", type=UUID)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 86400 or args.export.exists():
        raise ValueError("BOUNDED_DURATION_AND_NEW_EXPORT_REQUIRED")
    config = Config.model_validate_json(args.config.read_text(encoding="utf-8-sig"))
    engine = create_engine(os.environ["TE_DATABASE_URL"])
    client = NativeObserverClient()
    if not client.initialize():
        raise ValueError("MT5_ATTACH_FAILED")
    try:
        account, terminal = client.account_info(), client.terminal_info()
        require_demo(account, terminal)
        if type(account.get("margin_mode")) is not int or account["margin_mode"] not in (0, 1, 2):
            raise ValueError("KNOWN_BROKER_POSITION_MODE_REQUIRED")
        catalog = {r["name"] for r in client.symbols_get()}
        if not set(config.symbols) <= catalog:
            raise ValueError("OBSERVED_SYMBOL_CATALOG_MISMATCH")
        install(engine)
        if args.resume:
            with engine.connect() as conn:
                session = get_session(conn, args.resume)
            if session.config != config or session.account_scope != account_identity(account):
                raise ValueError("RESUME_SESSION_MISMATCH")
        else:
            session = ObservationSession(
                session_id=uuid4(),
                account_scope=account_identity(account),
                broker=account["company"],
                server_scope=account["server"],
                margin_mode=account["margin_mode"],
                started_at=datetime.now(UTC),
                terminal_build=terminal["build"],
                config=config,
            )
        observer = Observer(client, engine, session)
        tracemalloc.start()
        started, cpu = time.perf_counter(), time.process_time()
        with ObserverServer(engine, args.port) as server:
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                while time.perf_counter() - started < args.seconds:
                    tick = time.perf_counter()
                    observer.step()
                    time.sleep(max(0.05, config.poll_ms / 1000 - (time.perf_counter() - tick)))
            finally:
                observer.stop(datetime.now(UTC))
                server.shutdown()
                worker.join(5)
        elapsed = time.perf_counter() - started
        measurements = {
            "wall_seconds": elapsed,
            "cpu_seconds": time.process_time() - cpu,
            "python_peak_bytes": tracemalloc.get_traced_memory()[1],
            "polls": observer.polls,
            "failures": observer.failures,
            "frames": observer.new_frames,
            "real_external_ea_smoke": "NOT_ATTESTED",
        }
        tracemalloc.stop()
        with engine.connect() as conn:
            export_session(conn, session, args.export)
        (args.export / "performance.json").write_text(
            json.dumps(measurements, indent=2), encoding="utf-8"
        )
        print(
            f"Observer session {session.session_id}; {observer.polls} polls; "
            f"{observer.failures} failures"
        )
        if observer.failures:
            raise ValueError("OBSERVER_SESSION_HAS_FAILED_POLLS")
    finally:
        client.shutdown()
        engine.dispose()


if __name__ == "__main__":
    main()
