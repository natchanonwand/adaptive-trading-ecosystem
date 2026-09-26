"""Descriptive diagnostics with explicit denominators; no strategy inference."""

from collections import Counter
from decimal import Decimal

from trading_ecosystem.campaigns.contracts import RealEaQualificationCampaign
from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.observer.context import TIMEFRAMES
from trading_ecosystem.observer.contracts import attribute


def diagnostics(
    spec: RealEaQualificationCampaign, source: Record, entries: list[Record], stop: Record
) -> Record:
    session = source["session"]
    if (
        session.session_id != spec.campaign_id
        or session.account_scope != spec.account_scope
        or session.config != spec.observer_config
        or session.broker != spec.broker
        or session.server_scope != spec.server
        or session.terminal_build != spec.terminal_build
    ):
        raise ValueError("CAMPAIGN_SOURCE_IDENTITY_MISMATCH")
    for frame in source["frames"]:
        if (
            frame.session_id != spec.campaign_id
            or frame.account.get("company") != spec.broker
            or frame.account.get("server") != spec.server
            or type(frame.account.get("trade_mode")) is not int
            or frame.account["trade_mode"] != 0
        ):
            raise ValueError("CAMPAIGN_FRAME_ACCOUNT_MISMATCH")
    known = [
        e
        for e in source["events"]
        if e["attribution"]["confidence"] == "KNOWN"
        and e["attribution"]["source"] == "EXTERNAL_EA"
        and e["attribution"]["candidate_id"] == spec.metadata.candidate.ea_id
    ]
    candidate_tickets = {e["values"].get("deal_ticket") for e in known} - {None}
    for episode in source["episodes"]:
        attribution = episode["attribution"]
        if candidate_tickets.intersection(episode["deal_tickets"]) and (
            attribution["confidence"] != "KNOWN"
            or attribution["source"] != "EXTERNAL_EA"
            or attribution.get("candidate_id") != spec.metadata.candidate.ea_id
        ):
            # Frozen research selects whole episodes. Do not let a known opening
            # label pull subsequent manual/unknown fills into candidate statistics.
            raise ValueError("MIXED_ATTRIBUTION_EPISODE_REQUIRES_REVIEW")
    if spec.metadata.attribution_valid_from is None or any(
        utc_timestamp(e["broker_at"] or e["observed_at"]) < spec.metadata.attribution_valid_from
        for e in known
    ):
        raise ValueError("EVENT_OUTSIDE_ATTESTED_BINDING_PERIOD")
    coverage = {}
    for tf in TIMEFRAMES:
        available = sum(e["quality"].get(tf + "_history_count", 0) > 0 for e in entries)
        sufficient = sum(e["quality"].get(tf + "_history_sufficient") is True for e in entries)
        coverage[tf] = dict(
            entries=len(entries),
            available=available,
            sufficient_history=sufficient,
            available_fraction=available / len(entries) if entries else None,
            sufficient_fraction=sufficient / len(entries) if entries else None,
            gap_count=sum(e["quality"].get(tf + "_gaps", 0) for e in entries),
        )
    deals: dict[str, Record] = {}
    for frame in source["frames"]:
        for deal in frame.deals:
            binding = attribute(deal, spec.observer_config)
            if binding.confidence == "KNOWN" and binding.source == "EXTERNAL_EA":
                key = str(deal["ticket"])
                if key in deals and deals[key] != deal:
                    raise ValueError("CONFLICTING_CAMPAIGN_DEAL")
                deals[key] = deal
    costs = {}
    for name in ("commission", "fee", "swap"):
        observed = [Decimal(str(d[name])) for d in deals.values() if d.get(name) is not None]
        costs[name] = dict(
            observed_sum=str(sum(observed, Decimal(0))) if observed else None,
            observed_deals=len(observed),
            unknown_deals=len(deals) - len(observed),
        )
    started = utc_timestamp(stop["started_at"])
    ended = utc_timestamp(stop["ended_at"])
    entry_events = [e for e in known if e["kind"] in {"POSITION_OPENED", "POSITION_INCREASED"}]
    inside = sum(
        started <= utc_timestamp(e["broker_at"] or e["observed_at"]) <= ended for e in entry_events
    )
    return dict(
        attribution=dict(Counter(e["attribution"]["confidence"] for e in source["events"])),
        market_context_coverage=coverage,
        observed_costs=costs,
        broker_exit_reason_codes=dict(
            Counter(
                str(d.get("reason", "UNKNOWN"))
                for d in deals.values()
                if d.get("entry") in (1, 2, 3)
            )
        ),
        direction_counts=dict(Counter(str(e.get("direction")) for e in entries)),
        symbol_counts=dict(Counter(e["symbol"] for e in entries)),
        distinct_sessions=len({e["session_id"] for e in entries}),
        during_observation_entry_events=inside,
        historical_recovered_entry_events=len(entry_events) - inside,
        events_ingested_per_hour=(
            len(source["events"]) * 3600 / stop["wall_seconds"]
            if stop["wall_seconds"] > 0
            else None
        ),
        events_rate_basis="INGESTION_INCLUDING_ATTESTED_HISTORY_NOT_LIVE_ENTRY_RATE",
        non_entry_denominator="NOT_COLLECTED; P(context|entry), NOT P(entry|context)",
    )
