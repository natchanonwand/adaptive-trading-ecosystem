"""Minimal immutable definition storage and append-only protocol violations."""

from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import Column, Connection, ForeignKey, String, Table, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert

from trading_ecosystem.experiments.contracts import ExperimentCampaign, ExperimentDefinition
from trading_ecosystem.tester import readiness
from trading_ecosystem.tester import store as baseline
from trading_ecosystem.workbench.store import metadata

records = Table(
    "experiment_definitions",
    metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, ForeignKey("workbench.projects.id"), nullable=False),
    Column("state", String, nullable=False),
    Column("body", JSONB, nullable=False),
)
violations = Table(
    "experiment_protocol_events",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "definition_id", String, ForeignKey("workbench.experiment_definitions.id"), nullable=False
    ),
    Column("body", JSONB, nullable=False),
)


def validate_baseline(conn: Connection, definition: ExperimentDefinition) -> None:
    project = baseline.project(conn, definition.project_id)
    config = readiness.get_configuration(conn, definition.baseline_configuration_id)
    spec = config["specification"]
    if (
        project.candidate_id != definition.candidate_id
        or spec["project_id"] != str(definition.project_id)
        or config["configuration_identity"] != definition.baseline_identity
        or project.broker_binding.broker_symbol != definition.symbol
        or project.broker_binding.timeframe != definition.timeframe
        or project.broker_binding.broker_name != definition.broker
        or project.broker_binding.environment != "DEMO"
    ):
        raise ValueError("EXPERIMENT_BASELINE_BINDING_MISMATCH")


def detail(conn: Connection, definition_id: UUID, lock: bool = False) -> dict[str, Any]:
    query = select(records).where(records.c.id == str(definition_id))
    if lock:
        query = query.with_for_update()
    row = conn.execute(query).mappings().one_or_none()
    if row is None:
        raise ValueError("EXPERIMENT_DEFINITION_NOT_FOUND")
    if row["state"] not in {"DRAFT", "FROZEN"}:
        raise ValueError("INVALID_EXPERIMENT_STATE")
    definition = ExperimentDefinition.model_validate(row["body"])
    if str(uuid5(NAMESPACE_URL, definition.identity)) != row["id"]:
        raise ValueError("EXPERIMENT_IDENTITY_MISMATCH")
    return {
        "id": row["id"],
        "state": row["state"],
        "identity": definition.identity,
        "definition": definition.model_dump(mode="json"),
        "parameter_space_identity": definition.parameter_space.identity,
        "split_plan_identity": definition.split_plan.identity,
        "campaign_identity": ExperimentCampaign(definition_identity=definition.identity).identity,
        "execution_enabled": False,
        "oos_access": "LOCKED_UNAVAILABLE_IN_PHASE_5C_0",
    }


def save(conn: Connection, definition: ExperimentDefinition) -> dict[str, Any]:
    validate_baseline(conn, definition)
    key = uuid5(NAMESPACE_URL, definition.identity)
    inserted = conn.execute(
        insert(records)
        .values(
            id=str(key),
            project_id=str(definition.project_id),
            state="DRAFT",
            body=definition.model_dump(mode="json"),
        )
        .on_conflict_do_nothing()
        .returning(records.c.id)
    ).scalar_one_or_none()
    result = detail(conn, key)
    if result["definition"] != definition.model_dump(mode="json"):
        raise ValueError("IMMUTABLE_DEFINITION_CONFLICT")
    if inserted is not None:
        audit(conn, key, "DEFINITION_REGISTERED", definition.identity)
    return result


def audit(conn: Connection, key: UUID, event: str, identity: str) -> None:
    conn.execute(
        insert(violations).values(
            id=str(uuid4()),
            definition_id=str(key),
            body={
                "event": event,
                "definition_identity": identity,
                "recorded_at": datetime.now(UTC).isoformat(),
            },
        )
    )


def freeze(conn: Connection, definition_id: UUID) -> dict[str, Any]:
    record = detail(conn, definition_id, lock=True)
    validate_baseline(conn, ExperimentDefinition.model_validate(record["definition"]))
    if record["state"] == "FROZEN":
        return record
    audit(conn, definition_id, "DEFINITION_FROZEN", record["identity"])
    conn.execute(update(records).where(records.c.id == str(definition_id)).values(state="FROZEN"))
    return detail(conn, definition_id)


def reject_action(conn: Connection, definition_id: UUID, action: str) -> dict[str, str]:
    record = detail(conn, definition_id, lock=True)
    event = {
        "event": "PROTOCOL_VIOLATION",
        "recorded_at": datetime.now(UTC).isoformat(),
        "action": action,
        "definition_identity": record["identity"],
        "reason": "PHASE_5C_0_EXECUTION_AND_MUTATION_FORBIDDEN",
    }
    conn.execute(
        insert(violations).values(id=str(uuid4()), definition_id=str(definition_id), body=event)
    )
    return event


def list_definitions(conn: Connection, project_id: UUID) -> list[dict[str, Any]]:
    baseline.project(conn, project_id)
    keys = conn.execute(
        select(records.c.id)
        .where(records.c.project_id == str(project_id))
        .order_by(records.c.id)
        .limit(100)
    ).scalars()
    return [detail(conn, UUID(key)) for key in keys]
