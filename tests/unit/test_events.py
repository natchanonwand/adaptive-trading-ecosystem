from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tests.conftest import draft
from trading_ecosystem.domain.canonical import CanonicalPayload, canonical_bytes
from trading_ecosystem.domain.events import GENESIS_HASH, JournalEvent, seal_event
from trading_ecosystem.journal.contracts import IntegrityError, verify_chain


def test_canonical_types_order_scale_and_timezone() -> None:
    a = {"a": Decimal("1.00"), "b": [1, "1", True]}
    b = {"b": [1, "1", True], "a": Decimal("1")}
    assert canonical_bytes(a) == canonical_bytes(b)
    assert canonical_bytes(Decimal(1)) != canonical_bytes("1")
    assert canonical_bytes(Decimal("-0.00")) == canonical_bytes(Decimal(0))
    assert canonical_bytes(datetime(2026, 1, 1, tzinfo=UTC)) == canonical_bytes(
        datetime(2026, 1, 1, 7, tzinfo=timezone(timedelta(hours=7)))
    )
    with pytest.raises(ValueError):
        canonical_bytes({"money": 0.1})
    with pytest.raises(ValueError):
        canonical_bytes(datetime(2026, 1, 1))


def test_payload_is_deeply_immutable_and_hash_stable() -> None:
    original: dict[str, object] = {"items": [1]}
    payload = CanonicalPayload.from_mapping(original)
    before = payload.payload_hash
    original["items"] = [2]
    assert payload.payload_hash == before
    assert before == CanonicalPayload.from_mapping({"items": [1]}).payload_hash
    assert before != CanonicalPayload.from_mapping({"items": [2]}).payload_hash
    with pytest.raises(ValidationError):
        payload.canonical_json = "{}"  # type: ignore[misc]


def test_chain_serialization_and_metadata_tamper() -> None:
    first_draft = draft()
    first = seal_event(first_draft, 1, GENESIS_HASH)
    second = seal_event(draft(first.account_id), 2, first.event_hash)
    assert first == JournalEvent.model_validate_json(first.model_dump_json())
    assert verify_chain((first, second), first.account_id) == second.event_hash
    data = first.model_dump()
    data["actor"] = "tampered"
    with pytest.raises(ValidationError):
        JournalEvent.model_validate(data)
    data = first.model_dump()
    data["payload"] = CanonicalPayload.from_mapping({"count": 2}).model_dump()
    with pytest.raises(ValidationError):
        JournalEvent.model_validate(data)
    with pytest.raises(IntegrityError):
        verify_chain((second, first), first.account_id)
    with pytest.raises(IntegrityError):
        verify_chain(
            (first, seal_event(draft(first.account_id), 2, GENESIS_HASH)), first.account_id
        )


@pytest.mark.parametrize(
    "text", ["{}", '["map",[["a",["int","01"]]]]', '["map",[["a",["float",1.0]]]]']
)
def test_noncanonical_payload_rejected(text: str) -> None:
    with pytest.raises(ValidationError):
        CanonicalPayload(canonical_json=text)
