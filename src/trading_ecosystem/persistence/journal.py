"""Caller-owned transactions; per-account row lock and atomic head/event writes."""

from uuid import UUID

from sqlalchemy import Connection, RowMapping, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.domain.events import GENESIS_HASH, EventDraft, JournalEvent, seal_event
from trading_ecosystem.journal.contracts import (
    DuplicateEventError,
    IntegrityError,
    JournalStorageError,
    verify_chain,
)
from trading_ecosystem.persistence.schema import journal_events, journal_heads


def _read_event(row: RowMapping) -> JournalEvent:
    try:
        event = JournalEvent.model_validate_json(row["body"])
        if (
            event.account_id != row["account_id"]
            or event.account_sequence != row["account_sequence"]
            or event.event_id != row["event_id"]
            or event.event_hash != row["event_hash"]
        ):
            raise ValueError
        return event
    except ValueError:
        raise IntegrityError("stored journal integrity failure") from None


class PostgresJournal:
    def __init__(self, connection: Connection) -> None:
        if connection.dialect.name != "postgresql":
            raise ValueError("PostgreSQL required")
        self._connection = connection

    def append(self, draft: EventDraft) -> JournalEvent:
        result = None
        failed = False
        try:
            with self._connection.begin_nested():
                result = self._append(draft)
        except SQLAlchemyError:
            failed = True
        if failed or result is None:
            raise JournalStorageError("journal transaction failed")
        return result

    def _append(self, draft: EventDraft) -> JournalEvent:
        conn = self._connection
        conn.execute(
            pg_insert(journal_heads)
            .values(account_id=draft.account_id, sequence=0, event_hash=GENESIS_HASH)
            .on_conflict_do_nothing(index_elements=[journal_heads.c.account_id])
        )
        head = (
            conn.execute(
                select(journal_heads)
                .where(journal_heads.c.account_id == draft.account_id)
                .with_for_update()
            )
            .mappings()
            .one()
        )
        # Verify the existing chain before extending it, including the head anchor.
        self._replay_locked(draft.account_id, head)
        existing = (
            conn.execute(select(journal_events).where(journal_events.c.event_id == draft.event_id))
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            event = _read_event(existing)
            if event.draft() != draft:
                raise DuplicateEventError("event identifier conflicts with existing content")
            return event
        event = seal_event(draft, head["sequence"] + 1, head["event_hash"])
        conn.execute(
            insert(journal_events).values(
                account_id=event.account_id,
                account_sequence=event.account_sequence,
                event_id=event.event_id,
                event_hash=event.event_hash,
                body=event.model_dump_json(),
            )
        )
        conn.execute(
            update(journal_heads)
            .where(journal_heads.c.account_id == draft.account_id)
            .values(sequence=event.account_sequence, event_hash=event.event_hash)
        )
        return event

    def _replay_locked(self, account_id: UUID, head: RowMapping | None) -> tuple[JournalEvent, ...]:
        rows = self._connection.execute(
            select(journal_events)
            .where(journal_events.c.account_id == account_id)
            .order_by(journal_events.c.account_sequence)
        ).mappings()
        events = tuple(_read_event(row) for row in rows)
        final_hash = verify_chain(events, account_id)
        if head is None:
            if events:
                raise IntegrityError("journal head missing")
        elif head["sequence"] != len(events) or head["event_hash"] != final_hash:
            raise IntegrityError("journal head integrity failure")
        return events

    def replay(self, account_id: UUID) -> tuple[JournalEvent, ...]:
        result = None
        failed = False
        try:
            # A shared head lock prevents a concurrent append between head and rows.
            head = (
                self._connection.execute(
                    select(journal_heads)
                    .where(journal_heads.c.account_id == account_id)
                    .with_for_update(read=True)
                )
                .mappings()
                .one_or_none()
            )
            if head is None:
                # The read linearizes here; a later first append belongs to the next replay.
                return ()
            result = self._replay_locked(account_id, head)
        except SQLAlchemyError:
            failed = True
        if failed or result is None:
            raise JournalStorageError("journal replay failed")
        return result
