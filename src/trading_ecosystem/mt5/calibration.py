"""Bounded DEMO calculation CLI and immutable retained-observation readback."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, select, text

from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.monitoring.contracts import Scope
from trading_ecosystem.mt5.calculations import NativeCalculator
from trading_ecosystem.mt5.calibration_economics import BrokerEconomicsEvidence
from trading_ecosystem.mt5.calibration_matrix import calibrate_symbol
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.cost_profile import profile_deals, profile_spreads
from trading_ecosystem.mt5.economics import inspect_instrument
from trading_ecosystem.mt5.normalization import account_identity, normalize, number, timestamp
from trading_ecosystem.mt5.store import observations


def retained_observations(engine: Engine, scope: Scope) -> tuple[list[Record], Record]:
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        rows = (
            conn.execute(
                select(observations)
                .where(observations.c.scope_id == scope.stream_id)
                .order_by(observations.c.kind, observations.c.external_id, observations.c.body_hash)
            )
            .mappings()
            .all()
        )
        values = []
        for row in rows:
            if digest(canonical_bytes(row["body"])) != row["body_hash"]:
                raise ValueError("RETAINED_OBSERVATION_HASH_MISMATCH")
            values.append(
                {
                    "kind": row["kind"],
                    "external_id": row["external_id"],
                    "body_hash": row["body_hash"],
                    "body": row["body"],
                }
            )
    return values, {
        "observation_count": len(values),
        "content_digest": digest(canonical_bytes(values)),
    }


def require_demo(account: Record, terminal: Record) -> None:
    if type(account.get("trade_mode")) is not int or account["trade_mode"] != 0:
        raise ValueError("DEMO_ACCOUNT_REQUIRED")
    if account.get("currency") != "USD" or terminal.get("connected") is not True:
        raise ValueError("CONNECTED_USD_DEMO_REQUIRED")
    digits = account.get("currency_digits")
    if type(digits) is not int or not 0 <= digits <= 8:
        raise ValueError("CURRENCY_PRECISION_REQUIRED")


def run(client: NativeCalculator, engine: Engine, scope: Scope, aliases: dict[str, str]) -> Record:
    if set(aliases) != {"BTCUSD", "XAUUSD", "USTEC100"} or len(set(aliases.values())) != 3:
        raise ValueError("THREE_EXPLICIT_DISTINCT_ALIASES_REQUIRED")
    if not client.initialize():
        raise ValueError("MT5_INITIALIZE_FAILED")
    try:
        account, terminal = client.account_info(), client.terminal_info()
        require_demo(account, terminal)
        if scope.environment.value != "DEMO" or account_identity(account) != scope.account_id:
            raise ValueError("RETAINED_EVIDENCE_ACCOUNT_MISMATCH")
        retained, source = retained_observations(engine, scope)
        costs = profile_deals([r["body"] for r in retained if r["kind"] == "DEAL"])
        spreads = profile_spreads(
            [(r["external_id"], r["body"]) for r in retained if r["kind"] == "QUOTE"]
        )
        catalog = {r["name"] for r in client.symbols_get()}
        results = []
        for logical, broker in sorted(aliases.items()):
            if broker not in catalog:
                raise ValueError("EXPLICIT_ALIAS_NOT_DISCOVERED")
            at = datetime.now(UTC)
            metadata = client.symbol_info(broker)
            quote = normalize(client.symbol_info_tick(broker))
            quote_at = timestamp(quote["time"], quote.get("time_msc"))
            age = (at - quote_at).total_seconds()
            if not -1 <= age <= 30:
                raise ValueError("CURRENT_QUOTE_REQUIRED")
            snapshot = inspect_instrument(logical, broker, metadata, at, account["currency"])
            result = calibrate_symbol(
                client, snapshot, quote, account["currency_digits"], number(account["margin_free"])
            )
            groups = [g for g in costs["groups"] if g["symbol"] == broker]
            evidence = BrokerEconomicsEvidence(
                snapshot=snapshot,
                price_pnl_model="VALIDATED",
                volume_lattice="VALIDATED",
                tick_economics="VALIDATED",
                margin_estimate="VALIDATED",
                commission_model="OBSERVED_ONLY" if groups else "UNKNOWN",
                swap_model="OBSERVED_ONLY" if groups else "UNKNOWN",
                stop_constraints="OBSERVED_ONLY",
            )
            result.update(
                captured_at=at.isoformat(),
                evidence=evidence.model_dump(mode="json"),
                overall="PARTIAL",
                risk_sizing_ready=evidence.risk_sizing_ready,
                qualification_eligible=False,
                cost_observations=groups,
                spread_observations=spreads["symbols"].get(broker),
            )
            results.append(result)
        end_account, end_terminal = client.account_info(), client.terminal_info()
        require_demo(end_account, end_terminal)
        if account_identity(end_account) != account_identity(account):
            raise ValueError("ACCOUNT_CHANGED_DURING_CALIBRATION")
        for field in ("currency", "currency_digits", "leverage"):
            if end_account[field] != account[field]:
                raise ValueError("ACCOUNT_ECONOMICS_CHANGED_DURING_CALIBRATION")
        _, after = retained_observations(engine, scope)
        if source != after:
            raise ValueError("RETAINED_EVIDENCE_CHANGED_DURING_CALIBRATION")
        return {
            "schema_version": 1,
            "captured_at": datetime.now(UTC).isoformat(),
            "terminal_build": terminal["build"],
            "broker_company": account["company"],
            "server": account["server"],
            "account_currency": account["currency"],
            "currency_digits": account["currency_digits"],
            "leverage": account["leverage"],
            "account_kind": "DEMO",
            "observed_account_margin": str(number(account["margin"])),
            "observed_account_free_margin": str(number(account["margin_free"])),
            "source_evidence": source,
            "historical_costs": costs,
            "spreads": spreads,
            "experiment": {
                "equities": ["300", "3000", "30000"],
                "stop_ticks": [100, 10000, 200000, 500000],
                "profit_movements": [-100, -10, -1, 1, 10, 100],
                "commission_per_lot_per_side": "1",
                "commission_fixed_per_side": "0.01",
                "cost_basis": "EXPLICIT_SYNTHETIC_ASSUMPTIONS_NOT_BROKER_SCHEDULE",
                "health_basis": "SIMULATED_HEALTH_FOR_PURE_ENGINE_EXPERIMENT",
                "margin_basis": "PROPOSED_OPERATION_ESTIMATE_NOT_TOTAL_PORTFOLIO_MARGIN",
                "tolerance_basis": "TWO_HALF_UNIT_LEG_ROUNDINGS_PLUS_FOUR_INPUT_ULPS_PROPAGATED",
                "swap_basis": "NOT_MODELED_IN_INSTANTANEOUS_STOP_EXPERIMENT",
            },
            "symbols": results,
            "qualification_eligible": False,
            "risk_sizing_ready": False,
        }
    finally:
        client.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("CALIBRATION_OUTPUT_ALREADY_EXISTS")
    from trading_ecosystem.mt5.config import BridgeConfig

    config = BridgeConfig.model_validate_json(args.config.read_text(encoding="utf-8-sig"))
    source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    scope = Scope.model_validate(source["scope"])
    engine = create_engine(os.environ["TE_DATABASE_URL"])
    try:
        report = run(NativeCalculator(), engine, scope, config.aliases)
    finally:
        engine.dispose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    print(f"PASS: three DEMO calculator/domain matrices persisted to {args.output}")


if __name__ == "__main__":
    main()
