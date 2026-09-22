"""Transactional bridge checkpoints and immutable sanitized observations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Column, Connection, DateTime, Engine, MetaData, String, Table, Uuid, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.schema import CreateSchema

from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.monitoring import schema
from trading_ecosystem.monitoring.contracts import (
    EventInput,
    EventType,
    Payload,
    Scope,
    create_event,
)
from trading_ecosystem.monitoring.journal import TelemetryJournal
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import identity

metadata = MetaData(schema="mt5_readonly")
checkpoints = Table(
    "checkpoints",
    metadata,
    Column("scope_id", Uuid, primary_key=True),
    Column("body", JSONB, nullable=False),
    Column("body_hash", String(64), nullable=False),
)
observations = Table(
    "observations",
    metadata,
    Column("scope_id", Uuid, primary_key=True),
    Column("kind", String(32), primary_key=True),
    Column("external_id", String(160), primary_key=True),
    Column("body_hash", String(64), primary_key=True),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("body", JSONB, nullable=False),
)


def install(engine: Engine) -> None:
    """Idempotent additive schema v1 bootstrap; requires the existing monitoring migration."""
    with engine.begin() as conn:
        conn.execute(select(schema.heads.c.stream_id).limit(0))
        conn.execute(CreateSchema("mt5_readonly", if_not_exists=True))
        metadata.create_all(conn)


class Store:
    def __init__(self, conn: Connection, scope: Scope) -> None:
        self.conn, self.scope = conn, scope
        self.source = identity("MT5_READONLY_V1", scope.account_id)
        self.journal = TelemetryJournal(conn)
        # A scope row lock serializes concurrent bridge processes, including first startup.
        empty: Record = {"version": 1}
        conn.execute(
            insert(checkpoints)
            .values(scope_id=scope.stream_id, body=empty, body_hash=digest(canonical_bytes(empty)))
            .on_conflict_do_nothing()
        )
        row = (
            conn.execute(
                select(checkpoints)
                .where(checkpoints.c.scope_id == scope.stream_id)
                .with_for_update()
            )
            .mappings()
            .one()
        )
        if row["body_hash"] != digest(canonical_bytes(row["body"])):
            raise ValueError("BRIDGE_CHECKPOINT_INTEGRITY_FAILURE")
        self.state: Record = dict(row["body"])
        if self.state.get("version") != 1:
            raise ValueError("UNSUPPORTED_BRIDGE_CHECKPOINT_VERSION")
        source = (
            conn.execute(
                select(schema.sources).where(
                    schema.sources.c.stream_id == scope.stream_id,
                    schema.sources.c.source_instance_id == self.source,
                )
            )
            .mappings()
            .one_or_none()
        )
        self.sequence = source["sequence"] if source else 0
        self.last_time: datetime | None = source["occurred_at"] if source else None

    def save(self) -> None:
        self.conn.execute(
            checkpoints.update()
            .where(checkpoints.c.scope_id == self.scope.stream_id)
            .values(body=self.state, body_hash=digest(canonical_bytes(self.state)))
        )

    def observation(
        self, kind: str, external: str, body: Record, at: datetime, immutable: bool = False
    ) -> bool:
        rows = (
            self.conn.execute(
                select(observations).where(
                    observations.c.scope_id == self.scope.stream_id,
                    observations.c.kind == kind,
                    observations.c.external_id == external,
                )
            )
            .mappings()
            .all()
        )
        hashed = digest(canonical_bytes(body))
        for row in rows:
            if digest(canonical_bytes(row["body"])) != row["body_hash"]:
                raise ValueError("BROKER_OBSERVATION_INTEGRITY_FAILURE")
            if row["body_hash"] == hashed:
                return False
        if rows and immutable:
            raise ValueError("CONFLICTING_BROKER_IDENTITY")
        self.conn.execute(
            insert(observations).values(
                scope_id=self.scope.stream_id,
                kind=kind,
                external_id=external,
                body_hash=hashed,
                observed_at=at,
                body=body,
            )
        )
        return True

    def emit(
        self,
        event_type: EventType,
        payload: Payload,
        at: datetime,
        symbol: str | None = None,
        raw: Record | None = None,
    ) -> UUID:
        self.sequence += 1
        if self.last_time is not None and at < self.last_time:
            raise ValueError("OBSERVATION_CLOCK_REGRESSION")
        raw = raw or {}
        event = create_event(
            EventInput(
                event_type=event_type,
                scope=self.scope,
                occurred_at=at,
                recorded_at=at,
                source="ADAPTER",
                source_instance_id=self.source,
                source_sequence=self.sequence,
                correlation_id=self.scope.stream_id,
                symbol=symbol,
                broker_ticket=str(raw["ticket"]) if "ticket" in raw else None,
                magic_number=raw.get("magic")
                if type(raw.get("magic")) is int and 0 <= raw["magic"] < 2**63
                else None,
                comment=raw.get("comment"),
                payload=payload,
            )
        )
        self.journal.append(event)
        self.last_time = at
        return event.event_id

    def projected_positions(self) -> dict[str, Any]:
        rows = (
            self.conn.execute(
                select(schema.position_projection).where(
                    schema.position_projection.c.stream_id == self.scope.stream_id
                )
            )
            .mappings()
            .all()
        )
        result: dict[str, Any] = {}
        for row in rows:
            if digest(canonical_bytes(row["body"])) != row["body_hash"]:
                raise ValueError("PROJECTION_INTEGRITY_FAILURE_REBUILD_REQUIRED")
            if row["body"]["state"] == "OPEN":
                result[row["entity_id"]] = row["body"]
        return result
