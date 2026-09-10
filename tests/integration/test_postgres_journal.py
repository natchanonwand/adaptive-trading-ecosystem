from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import Engine, inspect, select, text, update
from sqlalchemy.exc import DBAPIError

from tests.conftest import draft
from trading_ecosystem.domain.canonical import CanonicalPayload
from trading_ecosystem.journal.contracts import DuplicateEventError, IntegrityError, verify_chain
from trading_ecosystem.persistence.journal import PostgresJournal
from trading_ecosystem.persistence.schema import journal_heads

pytestmark = pytest.mark.integration


def test_fresh_migration_append_commit_reload(database: Engine) -> None:
    assert set(inspect(database).get_table_names()) == {
        "alembic_version",
        "journal_events",
        "journal_heads",
    }
    event = draft()
    with database.begin() as conn:
        assert (
            conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0001_journal"
        )
        saved = PostgresJournal(conn).append(event)
    with database.begin() as conn:
        replay = PostgresJournal(conn).replay(event.account_id)
        assert replay == (saved,)
        assert verify_chain(replay, event.account_id) == saved.event_hash


def test_duplicate_exact_retry_and_conflict(database: Engine) -> None:
    event = draft()
    with database.begin() as conn:
        journal = PostgresJournal(conn)
        first = journal.append(event)
        assert journal.append(event) == first
        changed = event.model_copy(update={"payload": CanonicalPayload.from_mapping({"count": 9})})
        with pytest.raises(DuplicateEventError):
            journal.append(changed)
        assert journal.replay(event.account_id) == (first,)


def test_transaction_rollback_has_no_partial_state(database: Engine) -> None:
    event = draft()
    with database.connect() as conn:
        transaction = conn.begin()
        journal = PostgresJournal(conn)
        journal.append(event)
        journal.append(draft(event.account_id))
        transaction.rollback()
    with database.begin() as conn:
        assert PostgresJournal(conn).replay(event.account_id) == ()
        assert (
            conn.execute(
                select(journal_heads).where(journal_heads.c.account_id == event.account_id)
            ).first()
            is None
        )
        assert PostgresJournal(conn).append(event).account_sequence == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE journal_events SET body=body",
        "DELETE FROM journal_events",
        "TRUNCATE journal_events",
    ],
)
def test_database_forbids_rewriting_events(database: Engine, statement: str) -> None:
    with database.connect() as conn, pytest.raises(DBAPIError):
        with conn.begin():
            conn.execute(text(statement))


def test_privileged_tamper_is_detected_and_rolled_back(database: Engine) -> None:
    event = draft()
    with database.begin() as conn:
        saved = PostgresJournal(conn).append(event)
    # Deliberate corruption in a disposable DB as schema owner. Roll back the
    # trigger change and corrupt row together; normal application writes cannot do this.
    with database.connect() as conn:
        transaction = conn.begin()
        conn.execute(text("ALTER TABLE journal_events DISABLE TRIGGER journal_append_only"))
        conn.execute(
            text(
                "UPDATE journal_events SET body=replace(body, 'test-suite', 'bad-actor') "
                "WHERE event_id=:id"
            ),
            {"id": event.event_id},
        )
        with pytest.raises(IntegrityError):
            PostgresJournal(conn).replay(event.account_id)
        with pytest.raises(IntegrityError):
            PostgresJournal(conn).append(draft(event.account_id))
        transaction.rollback()
    with database.begin() as conn:
        assert PostgresJournal(conn).replay(event.account_id) == (saved,)


def test_head_tampering_detected(database: Engine) -> None:
    event = draft()
    with database.begin() as conn:
        PostgresJournal(conn).append(event)
    with database.connect() as conn:
        transaction = conn.begin()
        conn.execute(
            update(journal_heads)
            .where(journal_heads.c.account_id == event.account_id)
            .values(sequence=8)
        )
        with pytest.raises(IntegrityError):
            PostgresJournal(conn).replay(event.account_id)
        transaction.rollback()


def test_concurrent_appends_are_serialized(database: Engine) -> None:
    account = uuid4()

    def append_one(_: int) -> int:
        with database.begin() as conn:
            return PostgresJournal(conn).append(draft(account)).account_sequence

    with ThreadPoolExecutor(max_workers=4) as pool:
        sequences = list(pool.map(append_one, range(12)))
    assert sorted(sequences) == list(range(1, 13))
    with database.begin() as conn:
        events = PostgresJournal(conn).replay(account)
        assert len(events) == 12
        verify_chain(events, account)


def test_concurrent_duplicate_is_idempotent(database: Engine) -> None:
    event = draft()

    def append_same(_: int) -> str:
        with database.begin() as conn:
            return PostgresJournal(conn).append(event).event_hash

    with ThreadPoolExecutor(max_workers=3) as pool:
        hashes = list(pool.map(append_same, range(3)))
    assert len(set(hashes)) == 1
    with database.begin() as conn:
        assert len(PostgresJournal(conn).replay(event.account_id)) == 1


@settings(
    max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None
)
@given(st.lists(st.booleans(), min_size=1, max_size=12))
def test_journal_commit_rollback_properties(database: Engine, commit_flags: list[bool]) -> None:
    account = uuid4()
    committed = []
    for commit in commit_flags:
        with database.connect() as conn:
            transaction = conn.begin()
            event = PostgresJournal(conn).append(draft(account))
            if commit:
                transaction.commit()
                committed.append(event)
            else:
                transaction.rollback()
    with database.begin() as conn:
        journal = PostgresJournal(conn)
        assert journal.replay(account) == tuple(committed)
        assert journal.replay(account) == tuple(committed)
        assert [event.account_sequence for event in committed] == list(range(1, len(committed) + 1))
