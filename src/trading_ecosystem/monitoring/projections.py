"""Copy typed authoritative observations into transactional, disposable read models."""

from typing import Any

from sqlalchemy import Connection, Table, select
from sqlalchemy.dialects.postgresql import insert

from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.monitoring import schema
from trading_ecosystem.monitoring.contracts import HealthView, PositionView, RiskView, StoredEvent


def apply_projection(conn: Connection, stored: StoredEvent) -> None:
    event = stored.event
    payload = event.payload
    kind = payload.kind
    table = {
        "ACCOUNT": schema.account_snapshots,
        "PORTFOLIO": schema.portfolio_snapshots,
        "POSITION": schema.position_projection,
        "RISK": schema.risk_projection,
        "HEALTH": schema.system_health_projection,
        "ACTIVITY": schema.activity_projection,
    }[kind]
    if isinstance(payload, PositionView):
        entity = str(payload.episode_id)
    elif isinstance(payload, HealthView):
        entity = payload.component + ":" + str(event.source_instance_id)
    elif kind in {"ACCOUNT", "PORTFOLIO"}:
        entity = str(stored.sequence)  # Preserve valuation history, including UTC boundaries.
    elif kind == "RISK":
        entity = "account"
    else:
        entity = str(event.strategy_id or event.source_instance_id)
    previous = (
        conn.execute(
            select(table).where(
                table.c.stream_id == event.scope.stream_id, table.c.entity_id == entity
            )
        )
        .mappings()
        .one_or_none()
    )
    if kind in {"ACCOUNT", "PORTFOLIO"}:
        previous = (
            conn.execute(
                select(table)
                .where(table.c.stream_id == event.scope.stream_id)
                .order_by(table.c.sequence.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
    if previous is not None:
        if previous["body_hash"] != digest(canonical_bytes(previous["body"])):
            raise ValueError("PROJECTION_INTEGRITY_FAILURE_REBUILD_REQUIRED")
        if event.occurred_at < previous["occurred_at"]:
            raise ValueError("PROJECTION_TIME_REGRESSION")
    body = payload.model_dump(mode="json")
    body.update(
        environment=event.scope.environment.value,
        account_id=str(event.scope.account_id) if event.scope.account_id else None,
        run_id=str(event.scope.run_id) if event.scope.run_id else None,
        strategy_id=str(event.strategy_id) if event.strategy_id else None,
        symbol=event.symbol.value if event.symbol else None,
        source=event.source,
        source_instance_id=str(event.source_instance_id),
        magic_number=event.magic_number,
        broker_ticket=event.broker_ticket,
        comment=event.comment,
    )
    if isinstance(payload, PositionView):
        if event.event_type.value == "POSITION_OPENED":
            if previous is not None and event.corrects_event_id is None:
                raise ValueError("POSITION_ALREADY_EXISTS")
        elif previous is None:
            raise ValueError("POSITION_WITHOUT_OPEN_EVENT")
        if previous is not None:
            old = previous["body"]
            if old["state"] == "CLOSED" and (
                event.corrects_event_id is None or payload.state != "CLOSED"
            ):
                raise ValueError("CLOSED_POSITION_CANNOT_REOPEN")
            lineage = (
                "side",
                "strategy_id",
                "symbol",
                "opened_at",
                "source",
                "source_instance_id",
                "broker_ticket",
                "magic_number",
            )
            if any(old[key] != body[key] for key in lineage):
                raise ValueError("POSITION_LINEAGE_CHANGED")
    if isinstance(payload, RiskView):
        old = previous["body"] if previous is not None else {}
        body["last_rejection_reason"] = list(payload.rejection_reasons) or old.get(
            "last_rejection_reason"
        )
        body["last_state_change"] = (
            event.occurred_at.isoformat()
            if old.get("risk_state") != payload.risk_state
            else old.get("last_state_change")
        )
    _upsert(conn, table, entity, stored, body)
    if isinstance(payload, PositionView) and payload.state == "CLOSED":
        trade_data = (
            payload.trade.model_dump(mode="json")
            if payload.trade is not None
            else {
                "closed_at": event.occurred_at.isoformat(),
                "gross_pnl": None,
                "net_pnl": None,
                "net_r": None,
                "commission": None,
                "financing": None,
                "spread_cost": None,
                "outcome": "UNKNOWN",
                "complete": False,
            }
        )
        trade_body = {**body, **trade_data}
        _upsert(conn, schema.trade_projection, entity, stored, trade_body)


def _upsert(
    conn: Connection, table: Table, entity: str, stored: StoredEvent, body: dict[str, Any]
) -> None:
    values = {
        "stream_id": stored.event.scope.stream_id,
        "entity_id": entity,
        "sequence": stored.sequence,
        "event_id": stored.event.event_id,
        "occurred_at": stored.event.occurred_at,
        "body": body,
        "body_hash": digest(canonical_bytes(body)),
    }
    statement = insert(table).values(**values)
    conn.execute(
        statement.on_conflict_do_update(
            index_elements=[table.c.stream_id, table.c.entity_id],
            set_={
                key: value for key, value in values.items() if key not in {"stream_id", "entity_id"}
            },
        )
    )
