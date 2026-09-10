from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from trading_ecosystem.domain.events import GENESIS_HASH, EventDraft, JournalEvent


class JournalError(RuntimeError):
    pass


class DuplicateEventError(JournalError):
    pass


class IntegrityError(JournalError):
    pass


class JournalStorageError(JournalError):
    pass


class Journal(Protocol):
    def append(self, draft: EventDraft) -> JournalEvent: ...

    def replay(self, account_id: UUID) -> tuple[JournalEvent, ...]: ...


def verify_chain(events: Sequence[JournalEvent], account_id: UUID) -> str:
    previous = GENESIS_HASH
    for sequence, event in enumerate(events, 1):
        try:
            validated = JournalEvent.model_validate(event.model_dump())
        except ValueError:
            raise IntegrityError("event integrity failure") from None
        if (
            validated.account_id != account_id
            or validated.account_sequence != sequence
            or validated.previous_event_hash != previous
        ):
            raise IntegrityError("journal sequence or chain failure")
        previous = validated.event_hash
    return previous
