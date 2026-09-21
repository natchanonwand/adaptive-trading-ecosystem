from uuid import UUID

from sqlalchemy import Engine

from tests.phase34.fixtures import book, fill, quote, request
from trading_ecosystem.domain.canonical import CanonicalPayload
from trading_ecosystem.domain.events import EventDraft
from trading_ecosystem.domain.primitives import RuntimeMode
from trading_ecosystem.persistence.journal import PostgresJournal
from trading_ecosystem.portfolio.contracts import Observation
from trading_ecosystem.portfolio.fills import apply_fill
from trading_ecosystem.portfolio.projection import project
from trading_ecosystem.risk.contracts import Decision
from trading_ecosystem.risk.engine import evaluate_and_reserve


def test_risk_fill_accounting_journal_roundtrip(database: Engine) -> None:
    req = request()
    decision, reserved = evaluate_and_reserve(req)
    assert decision.order is not None and reserved[-1].reservations
    execution_fixture = fill(
        quantity=decision.order.volume, actual_price=decision.order.reference_entry
    )
    filled = apply_fill(book(), execution_fixture)
    snapshot = project((Observation(book=book()), Observation(book=filled, quotes=(quote(),))))
    assert snapshot.accounting.complete and snapshot.accounting.open_episode_count == 1
    assert Decision.model_validate_json(decision.model_dump_json()).identity == decision.identity
    event = EventDraft(
        event_id=UUID(int=34901),
        account_id=filled.cash.account_id,
        event_type="PHASE34_SYNTHETIC_PIPELINE",
        correlation_id=UUID(int=34902),
        actor="synthetic-integration-test",
        runtime_mode=RuntimeMode.BACKTEST,
        event_time=req.at,
        recorded_time=req.at,
        payload=CanonicalPayload.from_mapping(
            {"decision": decision.model_dump(), "snapshot": snapshot.model_dump()}
        ),
    )
    with database.begin() as connection:
        journal = PostgresJournal(connection)
        stored = journal.append(event)
        assert journal.append(event) == stored
    with database.begin() as connection:
        assert PostgresJournal(connection).replay(event.account_id) == (stored,)
