from datetime import timedelta
from typing import Any
from uuid import UUID

from tests.phase34.fixtures import T, request
from trading_ecosystem.monitoring.adapters import account_view, portfolio_view, risk_view
from trading_ecosystem.monitoring.contracts import (
    ActivityView,
    EventInput,
    EventType,
    HealthView,
    Payload,
    PositionView,
    Scope,
    TelemetryEvent,
    create_event,
)
from trading_ecosystem.portfolio.projection import project
from trading_ecosystem.risk.engine import evaluate


def telemetry(
    kind: EventType = EventType.SYSTEM_HEALTH, sequence: int = 1, **updates: Any
) -> TelemetryEvent:
    r = request()
    snapshot = project(r.history)
    at = T + timedelta(seconds=sequence)
    payload: Payload
    if kind == EventType.ACCOUNT_SNAPSHOT:
        payload = account_view(snapshot)
    elif kind == EventType.PORTFOLIO_SNAPSHOT:
        payload = portfolio_view(snapshot)
    elif kind.value.startswith("POSITION_"):
        payload = PositionView.model_validate(
            {
                "domain_identity": "synthetic",
                "episode_id": UUID(int=35002),
                "side": "LONG",
                "quantity": "0" if kind == EventType.POSITION_CLOSED else "0.10",
                "average_entry": "100",
                "mark_price": "101",
                "unrealized_pnl": "1",
                "realized_pnl": None,
                "stop_loss": "99",
                "take_profit": None,
                "opened_at": T,
                "updated_at": at,
                "state": "CLOSED" if kind == EventType.POSITION_CLOSED else "OPEN",
            }
        )
    elif kind.value.startswith("RISK_"):
        payload = risk_view(evaluate(r), snapshot)
        if kind == EventType.RISK_REJECTED:
            payload = payload.model_copy(update={"rejection_reasons": ("SYNTHETIC_REJECTION",)})
    elif kind.value.startswith(("BROKER_", "RECONCILIATION_")) or kind in {
        EventType.SYSTEM_HEALTH,
        EventType.EA_HEALTH,
    }:
        component = (
            "broker"
            if kind.value.startswith("BROKER_")
            else "reconciliation"
            if kind.value.startswith("RECONCILIATION_")
            else "ea"
            if kind == EventType.EA_HEALTH
            else "system"
        )
        state = {
            EventType.BROKER_DISCONNECTED: "DISCONNECTED",
            EventType.BROKER_STALE: "STALE",
            EventType.RECONCILIATION_MISMATCH: "ERROR",
            EventType.RECONCILIATION_STARTED: "DEGRADED",
        }.get(kind, "HEALTHY")
        payload = HealthView.model_validate({"component": component, "state": state})
    else:
        payload = ActivityView(status=kind.value)
    return create_event(
        EventInput.model_validate(
            {
                "event_type": kind,
                "scope": Scope(
                    environment="BACKTEST", account_id=UUID(int=35001), run_id=UUID(int=35003)
                ),
                "occurred_at": at,
                "recorded_at": at,
                "source": "DOMAIN",
                "source_instance_id": UUID(int=35004),
                "source_sequence": sequence,
                "strategy_id": UUID(int=35005),
                "symbol": "BTCUSD",
                "correlation_id": UUID(int=35006),
                "payload": payload,
                **updates,
            }
        )
    )
