"""Caller-owned PostgreSQL transactions, serialized append and deterministic rebuild."""

from typing import Any
from uuid import UUID

from sqlalchemy import Connection, delete, select, update
from sqlalchemy.dialects.postgresql import insert

from trading_ecosystem.domain.events import GENESIS_HASH
from trading_ecosystem.monitoring import schema
from trading_ecosystem.monitoring.contracts import (
    HealthView,
    PositionView,
    StoredEvent,
    TelemetryEvent,
    seal,
)
from trading_ecosystem.monitoring.projections import apply_projection


class TelemetryJournal:
    def __init__(self, connection: Connection) -> None:
        if connection.dialect.name != "postgresql":
            raise ValueError("POSTGRESQL_REQUIRED")
        self.connection = connection

    def replay(self, stream_id: UUID) -> tuple[StoredEvent, ...]:
        head = (
            self.connection.execute(
                select(schema.heads)
                .where(schema.heads.c.stream_id == stream_id)
                .with_for_update(read=True)
            )
            .mappings()
            .one_or_none()
        )
        rows = (
            self.connection.execute(
                select(schema.events)
                .where(schema.events.c.stream_id == stream_id)
                .order_by(schema.events.c.sequence)
            )
            .mappings()
            .all()
        )
        result: list[StoredEvent] = []
        previous_hash = GENESIS_HASH
        source_order: dict[UUID, tuple[int, str, Any]] = {}
        for sequence, row in enumerate(rows, 1):
            stored = StoredEvent.model_validate_json(row["body"])
            event = stored.event
            if (
                stored.sequence != sequence
                or stored.previous_hash != previous_hash
                or event.scope.stream_id != stream_id
                or row["event_id"] != event.event_id
                or row["sequence"] != sequence
                or row["source_sequence"] != event.source_sequence
                or row["source_instance_id"] != event.source_instance_id
                or row["event_type"] != event.event_type.value
                or row["occurred_at"] != event.occurred_at
                or row["recorded_at"] != event.recorded_at
            ):
                raise ValueError("TELEMETRY_CHAIN_OR_COLUMN_MISMATCH")
            last = source_order.get(event.source_instance_id)
            if event.source_sequence != (last[0] + 1 if last else 1) or (
                last and (last[1] != event.source or last[2] > event.occurred_at)
            ):
                raise ValueError("TELEMETRY_SOURCE_ORDER_MISMATCH")
            source_order[event.source_instance_id] = (
                event.source_sequence,
                event.source,
                event.occurred_at,
            )
            previous_hash = stored.event_hash
            result.append(stored)
        if head is None:
            if result:
                raise ValueError("TELEMETRY_HEAD_MISSING")
        elif (
            head["sequence"] != len(result)
            or head["event_hash"] != previous_hash
            or result
            and head["scope"] != result[0].event.scope.model_dump(mode="json")
        ):
            raise ValueError("TELEMETRY_HEAD_MISMATCH")
        source_rows = (
            self.connection.execute(
                select(schema.sources).where(schema.sources.c.stream_id == stream_id)
            )
            .mappings()
            .all()
        )
        actual = {
            r["source_instance_id"]: (r["sequence"], r["source"], r["occurred_at"])
            for r in source_rows
        }
        if actual != source_order:
            raise ValueError("TELEMETRY_SOURCE_HEAD_MISMATCH")
        return tuple(result)

    def append(self, event: TelemetryEvent) -> StoredEvent:
        event = TelemetryEvent.model_validate(event)
        conn = self.connection
        with conn.begin_nested():
            conn.execute(
                insert(schema.heads)
                .values(
                    stream_id=event.scope.stream_id,
                    scope=event.scope.model_dump(mode="json"),
                    sequence=0,
                    event_hash=GENESIS_HASH,
                )
                .on_conflict_do_nothing(index_elements=[schema.heads.c.stream_id])
            )
            head = (
                conn.execute(
                    select(schema.heads)
                    .where(schema.heads.c.stream_id == event.scope.stream_id)
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            existing = self.replay(event.scope.stream_id)
            for stored in existing:
                if stored.event.event_id == event.event_id:
                    if stored.event != event:
                        raise ValueError("CONFLICTING_TELEMETRY_DUPLICATE")
                    return stored
            source = next(
                (
                    s.event
                    for s in reversed(existing)
                    if s.event.source_instance_id == event.source_instance_id
                ),
                None,
            )
            if event.source_sequence != (source.source_sequence + 1 if source else 1):
                raise ValueError("SOURCE_SEQUENCE_GAP_OR_REORDER")
            if source is not None and (
                source.source != event.source or event.occurred_at < source.occurred_at
            ):
                raise ValueError("SOURCE_IDENTITY_OR_TIME_REGRESSION")
            if event.corrects_event_id is not None:
                corrected = next(
                    (s.event for s in existing if s.event.event_id == event.corrects_event_id), None
                )
                if (
                    corrected is None
                    or corrected.event_type != event.event_type
                    or corrected.source_instance_id != event.source_instance_id
                    or corrected.strategy_id != event.strategy_id
                    or corrected.symbol != event.symbol
                ):
                    raise ValueError("INVALID_CORRECTION_REFERENCE")
                if isinstance(event.payload, PositionView) and (
                    not isinstance(corrected.payload, PositionView)
                    or corrected.payload.episode_id != event.payload.episode_id
                ):
                    raise ValueError("CORRECTION_POSITION_MISMATCH")
                if isinstance(event.payload, HealthView) and (
                    not isinstance(corrected.payload, HealthView)
                    or corrected.payload.component != event.payload.component
                ):
                    raise ValueError("CORRECTION_COMPONENT_MISMATCH")
            stored = seal(event, head["sequence"] + 1, head["event_hash"])
            conn.execute(
                insert(schema.events).values(
                    stream_id=event.scope.stream_id,
                    sequence=stored.sequence,
                    event_id=event.event_id,
                    source_instance_id=event.source_instance_id,
                    source_sequence=event.source_sequence,
                    event_type=event.event_type.value,
                    occurred_at=event.occurred_at,
                    recorded_at=event.recorded_at,
                    body=stored.model_dump_json(),
                )
            )
            apply_projection(conn, stored)
            conn.execute(
                update(schema.heads)
                .where(schema.heads.c.stream_id == event.scope.stream_id)
                .values(sequence=stored.sequence, event_hash=stored.event_hash)
            )
            statement = insert(schema.sources).values(
                stream_id=event.scope.stream_id,
                source_instance_id=event.source_instance_id,
                source=event.source,
                sequence=event.source_sequence,
                occurred_at=event.occurred_at,
            )
            conn.execute(
                statement.on_conflict_do_update(
                    index_elements=[
                        schema.sources.c.stream_id,
                        schema.sources.c.source_instance_id,
                    ],
                    set_={"sequence": event.source_sequence, "occurred_at": event.occurred_at},
                )
            )
            return stored

    def rebuild(self, stream_id: UUID) -> int:
        """Rebuild only derived tables, atomically. Raw journal is never deleted."""
        conn = self.connection
        with conn.begin_nested():
            conn.execute(
                select(schema.heads).where(schema.heads.c.stream_id == stream_id).with_for_update()
            ).all()
            events = self.replay(stream_id)
            for table in schema.PROJECTIONS:
                conn.execute(delete(table).where(table.c.stream_id == stream_id))
            for stored in events:
                apply_projection(conn, stored)
        return len(events)
