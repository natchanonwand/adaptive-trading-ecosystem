"""Immutable envelopes. Chain hash includes metadata as well as payload hash."""

import hmac
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from trading_ecosystem.domain.canonical import CanonicalPayload, canonical_bytes, digest
from trading_ecosystem.domain.primitives import (
    AccountSequence,
    CausationId,
    CorrelationId,
    EntityId,
    FrozenModel,
    RuntimeMode,
    UtcTimestamp,
)

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GENESIS_HASH = "0" * 64


class EventDraft(FrozenModel):
    event_id: EntityId
    account_id: EntityId
    event_type: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    correlation_id: CorrelationId
    causation_id: CausationId | None = None
    actor: str = Field(min_length=1, max_length=100)
    runtime_mode: RuntimeMode
    release_reference: str | None = Field(default=None, max_length=200)
    event_time: UtcTimestamp
    recorded_time: UtcTimestamp
    schema_version: Literal[1] = 1
    payload: CanonicalPayload


class JournalEvent(EventDraft):
    account_sequence: AccountSequence
    payload_hash: Hash
    previous_event_hash: Hash
    event_hash: Hash

    @model_validator(mode="after")
    def check_hashes(self) -> Self:
        if not hmac.compare_digest(self.payload_hash, self.payload.payload_hash):
            raise ValueError("payload integrity failure")
        expected = digest(canonical_bytes(self.model_dump(mode="python", exclude={"event_hash"})))
        if not hmac.compare_digest(self.event_hash, expected):
            raise ValueError("event integrity failure")
        return self

    def draft(self) -> EventDraft:
        return EventDraft.model_validate(
            self.model_dump(
                exclude={"account_sequence", "payload_hash", "previous_event_hash", "event_hash"}
            )
        )


def seal_event(draft: EventDraft, sequence: int, previous_hash: str) -> JournalEvent:
    data = draft.model_dump(mode="python")
    data.update(
        account_sequence=sequence,
        payload_hash=draft.payload.payload_hash,
        previous_event_hash=previous_hash,
    )
    data["event_hash"] = digest(canonical_bytes(data))
    return JournalEvent.model_validate(data)
