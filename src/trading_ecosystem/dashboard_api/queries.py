"""Bounded display queries and Decimal aggregation of reported trade facts, not accounting."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Table, select

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.monitoring import schema
from trading_ecosystem.monitoring.queries import TABLES, read_events, read_view


def row_data(row: Any) -> dict[str, Any]:
    if row["body_hash"] != digest(canonical_bytes(row["body"])):
        raise ValueError("READ_MODEL_INTEGRITY_FAILURE")
    return {
        "sequence": row["sequence"],
        "event_id": str(row["event_id"]),
        "occurred_at": row["occurred_at"].astimezone(UTC).isoformat(),
        "values": row["body"],
    }


def streams(conn: Connection, after: UUID | None, limit: int) -> dict[str, Any]:
    statement = select(schema.heads).order_by(schema.heads.c.stream_id).limit(limit + 1)
    if after is not None:
        statement = statement.where(schema.heads.c.stream_id > after)
    rows = conn.execute(statement).mappings().all()
    items = [
        {"stream_id": str(r["stream_id"]), "scope": r["scope"], "cursor": r["sequence"]}
        for r in rows[:limit]
    ]
    return {
        "items": items,
        "next_cursor": items[-1]["stream_id"] if len(rows) > limit else None,
        "read_only": True,
    }


def snapshot(conn: Connection, stream: UUID) -> dict[str, Any]:
    # Handler starts REPEATABLE READ: all views and the SSE resume cursor share one snapshot.
    head = (
        conn.execute(select(schema.heads).where(schema.heads.c.stream_id == stream))
        .mappings()
        .one_or_none()
    )
    cursor = head["sequence"] if head else 0
    views: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for name in TABLES:
        try:
            views[name] = (
                collection(conn, stream, "positions", 0, 100, {})
                if name == "positions"
                else read_view(conn, name, stream, limit=100)
            )
            for item in views[name]["items"]:
                item["occurred_at"] = (
                    datetime.fromisoformat(item["occurred_at"]).astimezone(UTC).isoformat()
                )
        except (ValueError, RuntimeError):
            views[name] = None
            errors[name] = "READ_MODEL_INTEGRITY_FAILURE"
    events = read_events(conn, stream, max(0, cursor - 30), 30)
    return {
        "stream_id": str(stream),
        "scope": head["scope"] if head else None,
        "cursor": cursor,
        "views": views,
        "errors": errors,
        "events": [e.model_dump(mode="json") for e in events],
        "read_only": True,
    }


def window(start: str, end: str) -> tuple[datetime, datetime]:
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if not 0 < (last - first).days <= 366:
        raise ValueError("DATE_RANGE_REQUIRED_MAX_366_DAYS")
    return datetime.combine(first, datetime.min.time(), UTC), datetime.combine(
        last, datetime.min.time(), UTC
    )


def collection(
    conn: Connection, stream: UUID, name: str, after: int, limit: int, filters: dict[str, str]
) -> dict[str, Any]:
    table = {
        "trades": schema.trade_projection,
        "positions": schema.position_projection,
        "history": schema.account_snapshots,
    }[name]
    statement = select(table).where(table.c.stream_id == stream)
    for key in ("symbol", "strategy_id", "environment"):
        if filters.get(key):
            statement = statement.where(table.c.body[key].astext == filters[key])
    if name == "positions":
        statement = statement.where(table.c.body["state"].astext == "OPEN")
    if "start" in filters or "end" in filters:
        start, end = window(filters.get("start", ""), filters.get("end", ""))
        statement = statement.where(table.c.occurred_at >= start, table.c.occurred_at < end)
    # History is a bounded latest window. It never suggests an exhaustive historical curve.
    if name == "history":
        statement = statement.order_by(table.c.sequence.desc())
    else:
        statement = statement.where(table.c.sequence > after).order_by(table.c.sequence)
    rows = conn.execute(statement.limit(limit + 1)).mappings().all()
    items = [row_data(r) for r in rows[:limit]]
    if name == "history":
        items.reverse()
    return {
        "items": items,
        "next_cursor": rows[limit - 1]["sequence"] if len(rows) > limit else None,
        "has_more": len(rows) > limit,
        "read_only": True,
        "stream_id": str(stream),
    }


def calendar(conn: Connection, stream: UUID, start: str, end: str) -> dict[str, Any]:
    first, last = window(start, end)
    if (last - first).days > 31:
        raise ValueError("CALENDAR_MAX_31_DAYS")
    table: Table = schema.trade_projection
    rows = (
        conn.execute(
            select(table)
            .where(
                table.c.stream_id == stream,
                table.c.occurred_at >= first,
                table.c.occurred_at < last,
            )
            .order_by(table.c.sequence)
            .limit(10001)
        )
        .mappings()
        .all()
    )
    if len(rows) > 10000:
        return {
            "days": [],
            "partial": True,
            "reason": "MONTH_EXCEEDS_10000_TRADES",
            "read_only": True,
        }
    days: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        values = row_data(row)["values"]
        days[row["occurred_at"].astimezone(UTC).date().isoformat()].append(values)
    result = []
    for offset in range((last - first).days):
        day = (first + timedelta(days=offset)).date().isoformat()
        observations = days[day]
        item: dict[str, Any] = {
            "date": day,
            "trade_count": len(observations) if observations else None,
            "coverage": "OBSERVED_TRADES_ONLY" if observations else "NO_OBSERVATIONS",
            "max_intraday_drawdown": None,
        }
        with arithmetic_context():
            for field in (
                "net_pnl",
                "gross_pnl",
                "net_r",
                "commission",
                "financing",
                "spread_cost",
            ):
                values = [o.get(field) for o in observations]
                item[field] = (
                    str(sum((Decimal(v) for v in values if v is not None), Decimal(0)))
                    if (values and all(v is not None for v in values))
                    else None
                )
        outcomes = [o.get("outcome") for o in observations]
        for field, outcome in (("wins", "WIN"), ("losses", "LOSS")):
            item[field] = (
                outcomes.count(outcome)
                if outcomes and all(o in {"WIN", "LOSS", "FLAT"} for o in outcomes)
                else None
            )
        result.append(item)
    return {
        "days": result,
        "partial": False,
        "read_only": True,
        "basis": "UTC_CLOSED_EPISODES_REPORTED_VALUES_NOT_ACCOUNT_DAILY_PNL",
    }
