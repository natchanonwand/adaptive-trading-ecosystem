"""Local demo observer runner. Uses the already logged-in terminal, no credentials."""

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from socket import socket
from threading import Thread

from sqlalchemy import select

from trading_ecosystem.config.settings import load_settings
from trading_ecosystem.dashboard_api.server import DashboardServer
from trading_ecosystem.monitoring.journal import TelemetryJournal
from trading_ecosystem.monitoring.queries import read_view
from trading_ecosystem.mt5.bridge import Bridge
from trading_ecosystem.mt5.client import NativeReadClient, Record
from trading_ecosystem.mt5.config import BridgeConfig
from trading_ecosystem.mt5.store import checkpoints, install, observations
from trading_ecosystem.persistence.database import create_database_engine


class LocalDemoServer(DashboardServer):
    def handle_error(self, request: socket | tuple[bytes, socket], client_address: object) -> None:
        # Closing/reloading a browser aborts its SSE socket normally on Windows.
        if isinstance(sys.exception(), ConnectionError):
            return
        super().handle_error(request, client_address)


def evidence(bridge: Bridge, succeeded: int, failed: int) -> Record:
    with bridge.engine.begin() as conn:
        chain = TelemetryJournal(conn).replay(bridge.scope.stream_id)
        saved = (
            conn.execute(
                select(checkpoints.c.body).where(checkpoints.c.scope_id == bridge.scope.stream_id)
            ).scalar_one_or_none()
            or {}
        )
        records = (
            conn.execute(
                select(observations).where(observations.c.scope_id == bridge.scope.stream_id)
            )
            .mappings()
            .all()
        )
        latest: dict[str, Record] = {}
        counts: dict[str, int] = {}
        for row in sorted(records, key=lambda r: r["observed_at"]):
            counts[row["kind"]] = counts.get(row["kind"], 0) + 1
            if row["kind"] in {"INSTRUMENT", "TERMINAL", "ACCOUNT"}:
                latest[row["kind"] + ":" + row["external_id"]] = row["body"]
        return dict(
            scope=bridge.scope.model_dump(mode="json"),
            succeeded_cycles=succeeded,
            failed_cycles=failed,
            state=bridge.state.value,
            refused=bridge.refused,
            journal_verified=True,
            event_count=len(chain),
            head_hash=chain[-1].event_hash if chain else None,
            observations=counts,
            latest=latest,
            position_count=len(saved.get("positions", {})),
            order_count=len(saved.get("orders", {})),
            history_until=saved.get("history_until"),
            history_from=saved.get("history_from"),
            deal_watermark=saved.get("deal_watermark"),
            account_projection=read_view(conn, "account", bridge.scope.stream_id),
            read_only=True,
            qualification_sizing_eligible=False,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only MT5 DEMO monitoring; no trading authority"
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seconds", type=int, default=0, help="0 runs until Ctrl+C")
    parser.add_argument(
        "--evidence", type=Path, help="New local ignored JSON report (never overwritten)"
    )
    args = parser.parse_args()
    if args.seconds < 0:
        parser.error("seconds must be nonnegative")
    if args.evidence and args.evidence.exists():
        parser.error("evidence path already exists")
    config = BridgeConfig.model_validate_json(args.config.read_text(encoding="utf-8-sig"))
    settings = load_settings()
    if settings.database_url is None:
        parser.error("TE_DATABASE_URL required; migrate monitoring schema first")
    assert settings.database_url is not None
    engine = create_database_engine(settings.database_url)
    bridge: Bridge | None = None
    try:
        install(engine)
        bridge = Bridge(NativeReadClient(), engine, config)
        with LocalDemoServer(engine, args.port) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            print(
                f"Read-only API http://127.0.0.1:{server.server_port}; "
                "dashboard http://127.0.0.1:5173 (start npm run dev separately)",
                flush=True,
            )
            started = time.monotonic()
            succeeded = failed = 0
            try:
                while not args.seconds or time.monotonic() - started < args.seconds:
                    if bridge.step(datetime.now(UTC)):
                        succeeded += 1
                    else:
                        failed += 1
                    if bridge.refused:
                        print(
                            "REAL/UNKNOWN OR UNSUPPORTED ACCOUNT: QUALIFICATION REFUSED", flush=True
                        )
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                try:
                    if args.evidence:
                        report = evidence(bridge, succeeded, failed)
                        args.evidence.parent.mkdir(parents=True, exist_ok=True)
                        with args.evidence.open("x", encoding="utf-8") as out:
                            json.dump(report, out, indent=2)
                finally:
                    bridge.stop(datetime.now(UTC))
                    server.shutdown()
                    thread.join(5)
        return 0 if succeeded and not bridge.refused else 1
    except Exception:
        # Native/driver exceptions can contain account or connection details.
        print("READ_ONLY_BRIDGE_FAILED; inspect sanitized telemetry and local configuration")
        return 1
    finally:
        if bridge is not None and bridge.attached:
            bridge.client.shutdown()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
