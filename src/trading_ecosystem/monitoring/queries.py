"""Bounded read-only queries; cursors belong to one explicit environment/run/account stream."""

from typing import Any
from uuid import UUID

from sqlalchemy import Connection, select

from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.monitoring import schema
from trading_ecosystem.monitoring.contracts import StoredEvent

TABLES = {
    "account": schema.account_snapshots,
    "portfolio": schema.portfolio_snapshots,
    "positions": schema.position_projection,
    "trades": schema.trade_projection,
    "risk": schema.risk_projection,
    "system": schema.system_health_projection,
    "activity": schema.activity_projection,
}


def read_view(
    conn: Connection, name: str, stream: UUID, after: int = 0, limit: int = 100
) -> dict[str, Any]:
    if (
        name not in TABLES
        or type(after) is not int
        or after < 0
        or type(limit) is not int
        or not 1 <= limit <= 1000
    ):
        raise ValueError("INVALID_QUERY")
    table = TABLES[name]
    scope = conn.execute(
        select(schema.heads.c.scope).where(schema.heads.c.stream_id == stream)
    ).scalar_one_or_none()
    statement = select(table).where(table.c.stream_id == stream, table.c.sequence > after)
    if name in {"account", "portfolio", "risk"}:
        statement = statement.order_by(table.c.sequence.desc()).limit(1)
    else:
        statement = statement.order_by(table.c.sequence).limit(limit)
    rows = conn.execute(statement).mappings().all()
    data = []
    for row in rows:
        if row["body_hash"] != digest(canonical_bytes(row["body"])):
            raise RuntimeError("READ_MODEL_INTEGRITY_FAILURE")
        data.append(
            {
                "sequence": row["sequence"],
                "event_id": str(row["event_id"]),
                "occurred_at": row["occurred_at"].isoformat(),
                "values": row["body"],
            }
        )
    return {
        "scope": scope,
        "stream_id": str(stream),
        "items": data,
        "next_cursor": max((row["sequence"] for row in rows), default=after),
        "read_only": True,
    }


def read_events(
    conn: Connection, stream: UUID, after: int = 0, limit: int = 100
) -> tuple[StoredEvent, ...]:
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("INVALID_QUERY")
    rows = (
        conn.execute(
            select(schema.events)
            .where(schema.events.c.stream_id == stream, schema.events.c.sequence > after)
            .order_by(schema.events.c.sequence)
            .limit(limit)
        )
        .mappings()
        .all()
    )
    result: list[StoredEvent] = []
    previous = (
        conn.execute(
            select(schema.events.c.body).where(
                schema.events.c.stream_id == stream, schema.events.c.sequence == after
            )
        ).scalar_one_or_none()
        if after
        else None
    )
    previous_hash = StoredEvent.model_validate_json(previous).event_hash if previous else "0" * 64
    for row in rows:
        stored = StoredEvent.model_validate_json(row["body"])
        if (
            stored.sequence != after + len(result) + 1
            or stored.previous_hash != previous_hash
            or stored.sequence != row["sequence"]
            or stored.event.scope.stream_id != stream
            or stored.event.event_id != row["event_id"]
        ):
            raise RuntimeError("EVENT_READ_INTEGRITY_FAILURE")
        result.append(stored)
        previous_hash = stored.event_hash
    return tuple(result)
