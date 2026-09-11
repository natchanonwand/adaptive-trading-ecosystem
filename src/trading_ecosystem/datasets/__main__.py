"""Explicit Phase 2B CLI; outputs restricted to Git-ignored local evidence."""

import argparse
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from trading_ecosystem.datasets.contracts import Window
from trading_ecosystem.datasets.engine import ingest
from trading_ecosystem.datasets.verify import verify
from trading_ecosystem.discovery.contracts import DemoRequired, DiscoveryError
from trading_ecosystem.discovery.provider import Mt5ReadOnlyProvider
from trading_ecosystem.discovery.sdk import NativeSdk
from trading_ecosystem.domain.primitives import Asset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingest", action="store_true", required=True)
    parser.parse_args()
    root = Path("data/datasets")
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "data/datasets/probe.json"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print("BLOCKED: DATA_DIRECTORY_NOT_IGNORED")
        return 2
    window = Window(requested_start="2021-01-01T00:00:00Z", requested_end="2026-09-10T14:00:00Z")
    run = root / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    failed = False
    try:
        with Mt5ReadOnlyProvider(NativeSdk()) as provider:
            for asset in Asset:
                print(f"Ingesting {asset.value} H1", flush=True)
                try:
                    ingest(provider, asset, window, run / asset.value)
                    manifest = verify(run / asset.value)
                    print(
                        f"PASS {asset.value}: {manifest.bar_count} bars; {manifest.dataset_id}",
                        flush=True,
                    )
                except DemoRequired:
                    raise
                except DiscoveryError:
                    failed = True
                    print(
                        f"BLOCKED {asset.value}: read/validation failure; evidence retained",
                        flush=True,
                    )
    except DiscoveryError:
        print("BLOCKED: provider safety/read gate; native diagnostics suppressed")
        return 2
    print(f"Evidence: {run}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
