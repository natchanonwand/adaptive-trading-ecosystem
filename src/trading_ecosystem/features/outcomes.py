"""Post-entry episode measurements, never imported into causal feature columns."""

from decimal import Decimal

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.features.indicators import quantile
from trading_ecosystem.features.registry import CATALOG
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import number


def episode_outcome(episode: Record, events: list[Record]) -> Record:
    result: Record = {d.name: None for d in CATALOG if not d.causal}
    tickets = set(episode["deal_tickets"])
    fills = sorted(
        [e for e in events if e["values"].get("deal_ticket") in tickets],
        key=lambda e: (e["broker_at"], e["event_id"]),
    )
    entries = [e for e in fills if e["kind"] in {"POSITION_OPENED", "POSITION_INCREASED"}]
    partials = [e for e in fills if e["kind"] == "POSITION_REDUCED"]
    complete = (
        episode["complete"]
        and episode["closed_at"] is not None
        and episode["episode_confidence"] != "AMBIGUOUS"
    )
    result.update(
        close_status="CONFIRMED_CLOSED" if episode["closed_at"] else "UNRESOLVED_OR_OPEN",
        episode_confidence=episode["episode_confidence"],
        exit_time_known=episode["closed_at"] is not None,
        holding_duration=episode["holding_seconds"] if complete else None,
        episode_entry_count=len(entries),
        increase_count=episode["scale_in_count"],
        entry_volume_sequence=[e["values"]["volume"] for e in entries],
        entry_price_sequence=[e["values"]["price"] for e in entries],
        partial_close_count=len(partials),
    )
    for key, source in (
        ("gross_observed_pnl", "gross_pnl"),
        ("net_observed_pnl", "net_observed_pnl"),
        ("commission", "commission"),
        ("fee", "fee"),
        ("swap", "swap"),
    ):
        result[key] = episode[source] if complete else None
    with arithmetic_context():
        ratios = [
            number(b["values"]["volume"]) / number(a["values"]["volume"])
            for a, b in zip(entries, entries[1:], strict=False)
        ]
        times = [
            Decimal(
                str((utc_timestamp(b["broker_at"]) - utc_timestamp(a["broker_at"])).total_seconds())
            )
            for a, b in zip(entries, entries[1:], strict=False)
        ]
        prices = [
            abs(number(b["values"]["price"]) - number(a["values"]["price"]))
            for a, b in zip(entries, entries[1:], strict=False)
        ]
        result["max_volume_ratio"] = str(max(ratios)) if ratios else None
        for key, values in (
            ("median_entry_spacing_time", times),
            ("median_entry_spacing_price", prices),
        ):
            median = quantile(values, Decimal(".5"))
            result[key] = str(median) if median is not None else None
        if partials:
            first = partials[0]
            result["fraction_closed_first"] = str(
                number(first["values"]["closed_volume"]) / number(first["values"]["old_volume"])
            )
            entered = sum((number(e["values"]["volume"]) for e in entries), Decimal(0))
            result["fraction_closed_total_before_final"] = (
                str(
                    sum((number(e["values"]["closed_volume"]) for e in partials), Decimal(0))
                    / entered
                )
                if entered and episode["opened_at"] and episode["episode_confidence"] != "AMBIGUOUS"
                else None
            )
            if episode["opened_at"]:
                result["time_to_first_partial_close"] = str(
                    Decimal(
                        str(
                            (
                                utc_timestamp(first["broker_at"])
                                - utc_timestamp(episode["opened_at"])
                            ).total_seconds()
                        )
                    )
                )
        start = min((utc_timestamp(e["observed_at"]) for e in fills), default=None)
        end = max(
            (utc_timestamp(e["observed_at"]) for e in fills if e["kind"] == "POSITION_CLOSED"),
            default=None,
        )
        for stop, kind in (("SL", "STOP_LOSS_CHANGED"), ("TP", "TAKE_PROFIT_CHANGED")):
            changes = [
                e
                for e in events
                if e["kind"] == kind
                and e["position_id"] == episode["position_id"]
                and e["values"].get("change") != "INITIAL"
                and start is not None
                and utc_timestamp(e["observed_at"]) >= start
                and (end is None or utc_timestamp(e["observed_at"]) <= end)
            ]
            result[stop + "_change_count"] = len(changes)
            result[stop + "_removed_count"] = sum(
                e["values"]["change"] == "REMOVED" for e in changes
            )
            if changes and episode["opened_at"]:
                result[stop + "_first_change_delay_observed"] = str(
                    Decimal(
                        str(
                            (
                                min(utc_timestamp(e["observed_at"]) for e in changes)
                                - utc_timestamp(episode["opened_at"])
                            ).total_seconds()
                        )
                    )
                )
    return result
