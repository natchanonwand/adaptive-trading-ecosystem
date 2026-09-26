"""Explicit foreground commands; no automatic campaign, EA activation or resume."""

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine

from trading_ecosystem.campaigns.contracts import RealEaQualificationCampaign
from trading_ecosystem.campaigns.finalize import finalize, validate
from trading_ecosystem.campaigns.health import inspect_health
from trading_ecosystem.campaigns.journal import status
from trading_ecosystem.campaigns.runtime import run
from trading_ecosystem.observer.native import NativeObserverClient


def evidence_path(path: Path) -> Path:
    base = Path(".local/phase4_e/campaigns").resolve()
    result = path.resolve()
    if not result.is_relative_to(base) or result == base:
        raise ValueError("CAMPAIGN_OUTPUT_MUST_USE_LOCAL_PHASE4_E_NAMESPACE")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("preflight", "run"):
        part = sub.add_parser(command)
        part.add_argument("--config", type=Path, required=True)
        if command == "run":
            part.add_argument("--output", type=Path, required=True)
            part.add_argument("--restart-after-seconds", type=int)
    for command in ("status", "finalize", "validate"):
        sub.add_parser(command).add_argument("--campaign", type=Path, required=True)
    args = parser.parse_args()
    if args.command in ("status", "validate"):
        output = (status if args.command == "status" else validate)(evidence_path(args.campaign))
    else:
        engine = create_engine(os.environ["TE_DATABASE_URL"])
        try:
            if args.command == "finalize":
                output = finalize(evidence_path(args.campaign), engine)
            else:
                spec = RealEaQualificationCampaign.model_validate_json(
                    args.config.read_text(encoding="utf-8-sig")
                )
                # SDK initialization can launch a terminal; require one already running.
                processes = subprocess.run(
                    ["tasklist.exe", "/FI", "IMAGENAME eq terminal64.exe", "/FO", "CSV", "/NH"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).stdout
                if '"terminal64.exe"' not in processes.lower():
                    raise ValueError("USER_STARTED_MT5_TERMINAL_REQUIRED")
                client = NativeObserverClient()
                try:
                    if not client.initialize():
                        raise ValueError("MT5_ATTACH_FAILED")
                    if args.command == "preflight":
                        output = inspect_health(spec, client, engine, datetime.now(UTC))
                    else:
                        output = run(
                            spec,
                            client,
                            engine,
                            evidence_path(args.output),
                            restart_after_seconds=args.restart_after_seconds,
                        )
                finally:
                    client.shutdown()
        finally:
            engine.dispose()
    print(json.dumps(output, indent=2))
    if args.command == "preflight" and not output["passed"]:
        raise SystemExit(1)
    if args.command == "run" and output["status"] != "STOPPED_RECONCILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
