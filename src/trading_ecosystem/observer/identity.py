"""Observed source instances retain confidence and registry evidence, not magic-only claims."""

from trading_ecosystem.mt5.client import Record
from trading_ecosystem.observer.contracts import ObservationSession, content_id


def instances(session: ObservationSession, events: list[Record]) -> list[Record]:
    result: dict[str, Record] = {}
    for event in events:
        values = event["values"]
        row = values.get("position", values)
        if "magic" not in row:
            continue
        attribution = event["attribution"]
        key = content_id(
            [
                session.broker,
                session.server_scope,
                str(session.account_scope),
                attribution.get("candidate_id"),
                row.get("magic"),
                row.get("comment"),
                event["symbol"],
            ]
        )
        if key not in result:
            result[key] = {
                "source_instance_id": key,
                "broker": session.broker,
                "server_scope": session.server_scope,
                "account_scope": str(session.account_scope),
                "magic_number": row.get("magic"),
                "comment": row.get("comment"),
                "symbol": event["symbol"],
                "attribution": attribution,
                "first_seen_at": event["observed_at"],
                "last_seen_at": event["observed_at"],
            }
        result[key]["last_seen_at"] = event["observed_at"]
    return [result[key] for key in sorted(result)]
