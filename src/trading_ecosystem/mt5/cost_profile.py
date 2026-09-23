"""Descriptive retained-sample statistics, never a contractual future cost schedule."""

from collections import defaultdict
from decimal import ROUND_CEILING, Decimal

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import number


def distribution(values: list[Decimal]) -> Record:
    if not values:
        return {
            "sample_count": 0,
            "minimum": None,
            "median": None,
            "p90": None,
            "p95": None,
            "maximum": None,
        }
    with arithmetic_context():
        ordered = sorted(values)
        n = len(ordered)
        median = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2

        def percentile(percent: str) -> Decimal:
            index = int((Decimal(n) * Decimal(percent)).to_integral_value(ROUND_CEILING)) - 1
            return ordered[index]

        return {
            "sample_count": n,
            "minimum": str(ordered[0]),
            "median": str(median),
            "p90": str(percentile("0.90")),
            "p95": str(percentile("0.95")),
            "maximum": str(ordered[-1]),
        }


def profile_deals(deals: list[Record]) -> Record:
    unique: dict[str, Record] = {}
    duplicates = 0
    for deal in deals:
        ticket = deal.get("ticket")
        if type(ticket) is not int or ticket <= 0:
            raise ValueError("DEAL_IDENTITY_REQUIRED")
        key = str(ticket)
        if key in unique:
            if canonical_bytes(unique[key]) != canonical_bytes(deal):
                raise ValueError("CONFLICTING_DEAL_IDENTITY")
            duplicates += 1
        unique[key] = deal
    groups: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for deal in unique.values():
        groups[str(deal.get("symbol", "")), str(deal.get("entry", "UNKNOWN"))].append(deal)
    result: list[Record] = []
    with arithmetic_context():
        for (symbol, entry), rows in sorted(groups.items()):
            group: Record = {"symbol": symbol, "entry": entry, "deal_count": len(rows)}
            for field in ("commission", "fee", "swap"):
                raw, per_lot = [], []
                for row in rows:
                    if row.get(field) is None:
                        continue
                    value = number(row[field])
                    raw.append(value)
                    if row.get("volume") is not None and number(row["volume"]) > 0:
                        per_lot.append(value / number(row["volume"]))
                group[field] = {
                    "observed_count": len(raw),
                    "missing_count": len(rows) - len(raw),
                    "nonzero_count": sum(v != 0 for v in raw),
                    "per_lot": distribution(per_lot),
                    "classification": "OBSERVED_ONLY" if raw else "UNKNOWN",
                    "observed_zero_in_current_sample": bool(raw) and all(v == 0 for v in raw),
                }
            result.append(group)
    return {
        "deal_count": len(unique),
        "duplicate_count": duplicates,
        "history_completeness": "BOUNDED_RETAINED_SAMPLE",
        "contractually_validated": False,
        "groups": result,
    }


def profile_spreads(quotes: list[tuple[str, Record]]) -> Record:
    groups: dict[str, list[Decimal]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    with arithmetic_context():
        for symbol, quote in quotes:
            key = symbol, digest(canonical_bytes(quote))
            if key in seen:
                continue
            seen.add(key)
            spread = number(quote["ask"]) - number(quote["bid"])
            if spread < 0:
                raise ValueError("CROSSED_RETAINED_QUOTE")
            if quote.get("spread") is not None and number(quote["spread"]) != spread:
                raise ValueError("RETAINED_SPREAD_MISMATCH")
            groups[symbol].append(spread)
    return {
        "basis": "OBSERVED_DEMO_PERIOD_NOT_BACKTEST_COST_MODEL",
        "percentile_method": "NEAREST_RANK",
        "median_method": "MIDPOINT",
        "symbols": {s: distribution(v) for s, v in sorted(groups.items())},
    }
