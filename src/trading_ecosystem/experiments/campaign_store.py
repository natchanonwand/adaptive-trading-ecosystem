"""Transactional campaign ledger; one immutable ordered plan per frozen definition."""

from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Column, Connection, ForeignKey, String, Table, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert

from trading_ecosystem.experiments import campaigns, store
from trading_ecosystem.experiments.contracts import ExperimentDefinition, digest
from trading_ecosystem.workbench.store import metadata

records = Table(
    "experiment_campaigns",
    metadata,
    Column("id", String, primary_key=True),
    Column("definition_id", String, ForeignKey("workbench.experiment_definitions.id"), unique=True),
    Column("body", JSONB, nullable=False),
)


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def event(body: dict[str, Any], name: str, **details: Any) -> None:
    body["audit"].append({"event": name, "at": stamp(), **details})


def persist(conn: Connection, body: dict[str, Any]) -> None:
    payload = {"content": body, "identity": digest(body)}
    conn.execute(update(records).where(records.c.id == body["id"]).values(body=payload))


def read(conn: Connection, key: UUID, lock: bool = False) -> dict[str, Any]:
    query = select(records.c.body).where(records.c.id == str(key))
    if lock:
        query = query.with_for_update()
    payload = conn.execute(query).scalar_one_or_none()
    if payload is None:
        raise ValueError("CAMPAIGN_NOT_FOUND")
    body: dict[str, Any] = dict(payload["content"])
    if payload["identity"] != digest(body) or body["id"] != str(key):
        raise ValueError("CAMPAIGN_LEDGER_IDENTITY_MISMATCH")
    definition = ExperimentDefinition.model_validate(body["definition"])
    record = store.detail(conn, UUID(body["definition_id"]))
    if record["state"] != "FROZEN" or record["identity"] != definition.identity:
        raise ValueError("FROZEN_DEFINITION_CHANGED")
    plan = body["plan"]
    if plan["bindings"] != campaigns.bindings(definition) or body["plan_identity"] != digest(plan):
        raise ValueError("CAMPAIGN_PLAN_IDENTITY_MISMATCH")
    if str(uuid5(NAMESPACE_URL, body["plan_identity"])) != str(key):
        raise ValueError("CAMPAIGN_IDENTITY_MISMATCH")
    if body["selection"] is not None and body["selection_identity"] != digest(body["selection"]):
        raise ValueError("SELECTION_IDENTITY_MISMATCH")
    return body


def create(conn: Connection, definition_id: UUID, expected_identity: str) -> dict[str, Any]:
    record = store.detail(conn, definition_id, lock=True)
    if record["state"] != "FROZEN":
        raise ValueError("FROZEN_DEFINITION_REQUIRED")
    if record["identity"] != expected_identity:
        raise ValueError("EXPERIMENT_IDENTITY_MISMATCH")
    d = ExperimentDefinition.model_validate(record["definition"])
    store.validate_baseline(conn, d)
    existing = conn.execute(
        select(records.c.id).where(records.c.definition_id == str(definition_id))
    ).scalar_one_or_none()
    if existing:
        return read(conn, UUID(existing))
    plan = {
        "protocol": campaigns.PROTOCOL,
        "bindings": campaigns.bindings(d),
        "candidates": campaigns.generate(d),
        "selection_policy": "ALL_LEXICOGRAPHIC_TIES_OR_PARETO_FRONT_IN_CANDIDATE_ORDER",
        "duplicate_policy": "COLLAPSE_WITHOUT_REPLENISHING_ORDINAL_BUDGET",
        "failure_policy": "CONTINUE_WITHOUT_RETRY",
        "execution_budget_policy": "CONSERVATIVE_RESERVATION_BEFORE_HANDOFF",
    }
    identity = digest(plan)
    body: dict[str, Any] = {
        "id": str(uuid5(NAMESPACE_URL, identity)),
        "definition_id": str(definition_id),
        "definition": d.model_dump(mode="json"),
        "plan": plan,
        "plan_identity": identity,
        "status": "CREATED",
        "started_at": None,
        "deadline": None,
        "cancel_requested": False,
        "consumed_executions": 0,
        "runs": [],
        "selection": None,
        "selection_identity": None,
        "audit": [],
    }
    event(body, "ORDERED_PLAN_FROZEN")
    conn.execute(
        insert(records).values(
            id=body["id"],
            definition_id=str(definition_id),
            body={"content": body, "identity": digest(body)},
        )
    )
    return read(conn, UUID(body["id"]))


def list_for(conn: Connection, definition_id: UUID) -> list[dict[str, Any]]:
    keys = conn.execute(select(records.c.id).where(records.c.definition_id == str(definition_id)))
    return [read(conn, UUID(key)) for key in keys.scalars()]


def cancel(conn: Connection, key: UUID) -> dict[str, Any]:
    body = read(conn, key, True)
    if body["status"] in {"CREATED", "RUNNING"}:
        body["cancel_requested"] = True
        if body["status"] == "CREATED":
            body["status"] = "CANCELLED"
        event(body, "CANCELLATION_REQUESTED")
        persist(conn, body)
    return body
