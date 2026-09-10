from datetime import UTC, datetime
from uuid import UUID, uuid4

from trading_ecosystem.domain.canonical import CanonicalPayload
from trading_ecosystem.domain.events import EventDraft
from trading_ecosystem.domain.primitives import RuntimeMode


def draft(account_id: UUID | None = None) -> EventDraft:
    return EventDraft(
        event_id=uuid4(),
        account_id=account_id or uuid4(),
        event_type="FOUNDATION_TEST",
        correlation_id=uuid4(),
        actor="test-suite",
        runtime_mode=RuntimeMode.RESEARCH,
        event_time=datetime(2026, 9, 9, tzinfo=UTC),
        recorded_time=datetime(2026, 9, 9, tzinfo=UTC),
        payload=CanonicalPayload.from_mapping({"count": 1}),
    )
