"""Descriptive, confidence-filtered metrics; no behavioral labels or inferred edge."""

from decimal import Decimal

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.cost_profile import distribution
from trading_ecosystem.mt5.normalization import number


def summarize(episodes: list[Record], events: list[Record]) -> Record:
    selected = [e for e in episodes if e["ea_metrics_eligible"]]
    attributed = [
        e
        for e in episodes
        if e["attribution"]["source"] == "EXTERNAL_EA" and e["attribution"]["confidence"] == "KNOWN"
    ]
    direct_entries: dict[str, Record] = {}
    for event in events:
        a = event["attribution"]
        if (
            event["kind"] in {"POSITION_OPENED", "POSITION_STATE_OBSERVED"}
            and event["quality"] == "DIRECT"
            and a["source"] == "EXTERNAL_EA"
            and a["confidence"] == "KNOWN"
        ):
            direct_entries.setdefault(event["position_id"], event["values"])
    with arithmetic_context():
        result: Record = {
            "basis": "OBSERVED_KNOWN_EXTERNAL_EA_ONLY",
            "episodes": len(selected),
            "completed_episodes": sum(e["closed_at"] is not None for e in selected),
            "excluded_episodes": len(episodes) - len(selected),
            "buy_count": sum(e["direction"] == "BUY" for e in selected),
            "sell_count": sum(e["direction"] == "SELL" for e in selected),
            "symbols": sorted({e["symbol"] for e in selected}),
            "symbol_counts": {
                symbol: sum(e["symbol"] == symbol for e in selected)
                for symbol in sorted({e["symbol"] for e in selected})
            },
            "duration_count_basis": "ALL_KNOWN_EXTERNAL_EA_EPISODES_INCLUDING_PARTIAL",
            "known_duration_count": sum(e["holding_seconds"] is not None for e in attributed),
            "unknown_duration_count": sum(e["holding_seconds"] is None for e in attributed),
            "volume": distribution([number(v) for e in selected for v in e["entry_volumes"]]),
            "holding_seconds": distribution(
                [number(e["holding_seconds"]) for e in selected if e["holding_seconds"] is not None]
            ),
            "scale_in_count": sum(e["scale_in_count"] for e in selected),
            "partial_close_count": sum(e["partial_close_count"] for e in selected),
            "reversal_count_all_sources": sum(e["reversal_count"] for e in episodes),
            "mae": None,
            "mfe": None,
            "qualification_eligible": False,
        }
        for field in ("gross_pnl", "commission", "fee", "swap", "net_observed_pnl"):
            values = [e[field] for e in selected]
            result[field + "_known_count"] = sum(v is not None for v in values)
            result[field + "_unknown_count"] = sum(v is None for v in values)
            result[field] = (
                str(sum((number(v) for v in values), Decimal(0)))
                if values and None not in values
                else None
            )
        for field, distance in (("sl", "sl_distance"), ("tp", "tp_distance")):
            samples = [v for v in direct_entries.values() if "position" in v]
            present = [v for v in samples if number(v["position"].get(field) or 0) > 0]
            result[field + "_usage_rate"] = (
                str(Decimal(len(present)) / len(samples)) if samples else None
            )
            values = [number(v[distance]) for v in present if v.get(distance) is not None]
            result["average_" + distance] = (
                str(sum(values, Decimal(0)) / len(values)) if values else None
            )
        result["stop_usage_basis"] = "FIRST_OBSERVED_POSITION_STATE_NOT_ASSUMED_ENTRY_STATE"
        return result
