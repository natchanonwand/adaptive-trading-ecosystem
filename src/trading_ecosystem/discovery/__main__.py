"""Explicit operator-invoked discovery. Only sanitized summaries are persisted."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from trading_ecosystem.discovery.candidates import discover_candidates
from trading_ecosystem.discovery.contracts import (
    BarCoverage,
    DemoRequired,
    DiscoveryError,
    DiscoveryPlan,
    SymbolCandidate,
    TickCoverage,
)
from trading_ecosystem.discovery.provider import Mt5ReadOnlyProvider
from trading_ecosystem.discovery.sdk import NativeSdk
from trading_ecosystem.domain.primitives import Asset

OUTPUT_NAMES = (
    "provider_identity",
    "symbol_candidates",
    "instrument_metadata",
    "bar_coverage",
    "tick_coverage_probe",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="DEMO-only read-only MT5 discovery")
    parser.add_argument(
        "--catalog-only", action="store_true", help="collect catalog without historical requests"
    )
    args = parser.parse_args()
    directory = Path("data/discovery")
    directory.mkdir(parents=True, exist_ok=True)
    plan = DiscoveryPlan(as_of=datetime.now(UTC).replace(minute=0, second=0, microsecond=0))
    run = str(uuid4())
    output: dict[str, object] = {name: [] for name in OUTPUT_NAMES}
    status, reason = "OBSERVED", None
    try:
        with Mt5ReadOnlyProvider(NativeSdk()) as provider:
            output["provider_identity"] = provider.get_provider_identity().model_dump(mode="json")
            candidates = discover_candidates(provider.list_instruments())
            output["symbol_candidates"] = [
                candidate.model_dump(mode="json") for candidate in candidates
            ]
            metadata = []
            for candidate in candidates:
                entry: dict[str, object] = {"candidate": candidate.model_dump(mode="json")}
                try:
                    entry["metadata"] = provider.get_instrument_metadata(
                        candidate.broker_symbol
                    ).model_dump(mode="json")
                    try:
                        entry["quote"] = provider.get_latest_quote(
                            candidate.broker_symbol
                        ).model_dump(mode="json")
                    except DemoRequired:
                        raise
                    except DiscoveryError:
                        entry["quote_status"] = "UNAVAILABLE_OR_MALFORMED"
                except DemoRequired:
                    raise
                except DiscoveryError:
                    entry["metadata_status"] = "UNAVAILABLE"
                metadata.append(entry)
            output["instrument_metadata"] = metadata
            selected: list[SymbolCandidate] = []
            groups = {
                asset: sorted(
                    (candidate for candidate in candidates if candidate.canonical_asset == asset),
                    key=lambda candidate: (
                        candidate.match_basis != "EXACT_NAME",
                        candidate.currency_profit != "USD",
                        candidate.currency_base
                        != {Asset.BTCUSD: "BTC", Asset.XAUUSD: "XAU", Asset.USTEC100: "USD"}[asset],
                        len(candidate.broker_symbol),
                        candidate.broker_symbol,
                    ),
                )[: plan.max_candidates_per_asset]
                for asset in Asset
            }
            # Round-robin the assets so the global tick budget cannot be spent
            # on all alternatives of one canonical asset before another is probed.
            for index in range(plan.max_candidates_per_asset):
                selected.extend(group[index] for group in groups.values() if len(group) > index)
            bars: list[dict[str, object]] = []
            ticks: list[dict[str, object]] = []
            remaining = plan.max_ticks_total
            if not args.catalog_only:
                for index, candidate in enumerate(selected, 1):
                    print(f"Read-only coverage probe {index}/{len(selected)}", flush=True)
                    if remaining <= 0:
                        # Bar discovery still proceeds; no more tick requests are permitted.
                        from trading_ecosystem.discovery.probes import bar_intervals, probe_bars

                        bars.extend(
                            probe_bars(provider, candidate.broker_symbol, interval).model_dump(
                                mode="json"
                            )
                            for interval in bar_intervals(plan.as_of)
                        )
                        ticks.append(
                            {
                                "broker_symbol": candidate.broker_symbol,
                                "status": "GLOBAL_BUDGET_NOT_PROBED",
                            }
                        )
                        continue
                    candidate_plan = plan.model_copy(update={"max_ticks_total": remaining})
                    for observation in provider.probe_history_coverage(
                        candidate.broker_symbol, candidate_plan
                    ):
                        if isinstance(observation, BarCoverage):
                            bars.append(observation.model_dump(mode="json"))
                        elif isinstance(observation, TickCoverage):
                            remaining -= observation.tick_count
                            ticks.append(observation.model_dump(mode="json"))
                output["bar_coverage"], output["tick_coverage_probe"] = bars, ticks
            else:
                status = "CATALOG_ONLY_HISTORY_NOT_RUN"
            provider.get_account_environment()
    except DemoRequired:
        status, reason = "BLOCKED", "ACCOUNT_NOT_CONFIRMED_DEMO_OR_DISCONNECTED"
        output = {name: [] for name in OUTPUT_NAMES}
    except Exception:
        # Never serialize arbitrary exception messages, native records or tracebacks.
        status, reason = "BLOCKED", "DISCOVERY_FAILED_DETAILS_SUPPRESSED"
        output = {name: [] for name in OUTPUT_NAMES}
    for name in OUTPUT_NAMES:
        artifact = {
            "schema_version": 1,
            "run_id": run,
            "status": status,
            "reason": reason,
            "plan": plan.model_dump(mode="json"),
            "data": output[name],
        }
        temporary = directory / (name + ".tmp")
        temporary.write_text(
            json.dumps(artifact, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(directory / (name + ".json"))
    print(f"Discovery status: {status}; sanitized local evidence in data/discovery", flush=True)
    return 2 if status == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
