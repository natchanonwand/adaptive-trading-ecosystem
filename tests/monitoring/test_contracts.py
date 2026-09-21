from datetime import timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from tests.monitoring.fixtures import telemetry
from tests.phase34.fixtures import D, T, book, fill, quote, request
from trading_ecosystem.domain.primitives import RuntimeMode
from trading_ecosystem.monitoring.adapters import (
    account_view,
    portfolio_view,
    position_view,
    risk_view,
)
from trading_ecosystem.monitoring.contracts import (
    Environment,
    EventInput,
    EventType,
    Scope,
    StoredEvent,
    TelemetryEvent,
    create_event,
    seal,
)
from trading_ecosystem.portfolio.contracts import Observation
from trading_ecosystem.portfolio.fills import apply_fill
from trading_ecosystem.portfolio.projection import project
from trading_ecosystem.risk.engine import evaluate


@pytest.mark.parametrize("kind", list(EventType))
def test_all_event_types_roundtrip(kind: EventType) -> None:
    event = telemetry(kind)
    assert TelemetryEvent.model_validate_json(event.model_dump_json()) == event
    stored = seal(event, 1, "0" * 64)
    assert StoredEvent.model_validate_json(stored.model_dump_json()) == stored


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": 2},
        {"schema_version": True},
        {"schema_version": 1.0},
        {"occurred_at": T.replace(tzinfo=None)},
        {"event_id": UUID(int=99)},
        {"source_sequence": 0},
        {"read_only": False},
        {"read_only": 1},
    ],
)
def test_invalid_envelopes_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        telemetry().model_copy(update=changes)


def test_canonical_utc_and_decimal_scale() -> None:
    e = telemetry(EventType.ACCOUNT_SNAPSHOT)
    changed = e.model_copy(
        update={"occurred_at": e.occurred_at.astimezone(timezone(timedelta(hours=7)))}
    )
    assert changed.identity == e.identity
    assert changed.occurred_at.utcoffset() == timedelta(0)
    scaled = e.model_copy(update={"payload": e.payload.model_copy(update={"balance": "10000.000"})})
    assert seal(scaled, 1, "0" * 64).event_hash == seal(e, 1, "0" * 64).event_hash


def test_identity_excludes_delivery_payload_but_hash_protects_conflicts() -> None:
    e = telemetry()
    changed = e.model_copy(update={"comment": "different observation"})
    assert e.event_id == changed.event_id and e.identity != changed.identity
    with pytest.raises(ValidationError):
        seal(e, 1, "0" * 64).model_copy(update={"sequence": 2})


def test_environment_isolation_and_live_read_only() -> None:
    e = telemetry()
    live = Scope(environment=Environment.LIVE, account_id=e.scope.account_id, run_id=e.scope.run_id)
    data = e.model_dump(exclude={"event_id"})
    with pytest.raises(ValidationError, match="EXTERNAL_OBSERVATION"):
        create_event(EventInput.model_validate({**data, "scope": live}))
    external = create_event(
        EventInput.model_validate(
            {
                **data,
                "scope": live,
                "source": "EXTERNAL_EA",
                "strategy_id": None,
                "magic_number": 123,
                "broker_ticket": "fixture-ticket",
            }
        )
    )
    assert external.event_id != e.event_id and external.scope.stream_id != e.scope.stream_id
    assert external.read_only and "LIVE" not in RuntimeMode.__members__


@pytest.mark.parametrize("side,order_side", [("LONG", "BUY"), ("SHORT", "SELL")])
def test_authoritative_portfolio_and_position_copy(side: str, order_side: str) -> None:
    filled = apply_fill(book(), fill(direction=side, side=order_side))
    snapshot = project((Observation(book=book()), Observation(book=filled, quotes=(quote(),))))
    a = account_view(snapshot)
    p = portfolio_view(snapshot)
    position = position_view(snapshot, filled.positions[0].episode_id, T)
    assert p.account == a and a.equity == snapshot.accounting.equity
    assert (
        position.quantity == D("0.1")
        and position.unrealized_pnl == snapshot.marks[0].unrealized_pnl
    )
    assert position.mark_price == (quote().bid if side == "LONG" else quote().ask)
    assert position.realized_pnl is None and p.peak_equity is None


def test_risk_adapter_copies_pinned_limits_and_rejects_wrong_snapshot() -> None:
    r = request()
    s = project(r.history)
    decision = evaluate(r)
    view = risk_view(decision, s)
    assert view.risk_state == "ACTIVE" and view.risk_per_trade == D("0.0025")
    assert view.portfolio_risk_limit == D("0.0075")
    with pytest.raises(ValueError, match="SNAPSHOT_MISMATCH"):
        risk_view(decision, project((r.history[0],)))


@pytest.mark.parametrize(
    "field", ["balance", "equity", "realized_pnl", "unrealized_pnl", "used_margin", "free_margin"]
)
def test_monitoring_money_rejects_float(field: str) -> None:
    with pytest.raises(ValidationError):
        telemetry(EventType.ACCOUNT_SNAPSHOT).payload.model_copy(update={field: 0.1})
