"""Baseline state and normalized results in the existing Workbench PostgreSQL schema."""

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Column, Connection, ForeignKey, String, Table, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert

from trading_ecosystem.tester.contracts import Configuration, Result, Run, State, transition
from trading_ecosystem.workbench import store as onboarding
from trading_ecosystem.workbench.contracts import Project

runs = Table(
    "baseline_runs",
    onboarding.metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, ForeignKey("workbench.projects.id"), nullable=False),
    Column("body", JSONB, nullable=False),
)
results = Table(
    "baseline_results",
    onboarding.metadata,
    Column("id", String, ForeignKey("workbench.baseline_runs.id"), primary_key=True),
    Column("body", JSONB, nullable=False),
)


def get(conn: Connection, run_id: UUID, lock: bool = False) -> Run:
    query = select(runs.c.body).where(runs.c.id == str(run_id))
    if lock:
        query = query.with_for_update()
    body = conn.execute(query).scalar_one_or_none()
    if body is None:
        raise ValueError("BASELINE_RUN_NOT_FOUND")
    return Run.model_validate(body)


def project(conn: Connection, project_id: UUID) -> Project:
    body = conn.execute(
        select(onboarding.projects.c.body).where(onboarding.projects.c.id == str(project_id))
    ).scalar_one_or_none()
    if body is None:
        raise ValueError("PROJECT_NOT_FOUND")
    return Project.model_validate(body)


def create(conn: Connection, config: Configuration) -> Run:
    from sqlalchemy import text

    conn.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": config.baseline_run_id.int % (2**63 - 1)},
    )
    prior = conn.execute(
        select(runs.c.body).where(runs.c.id == str(config.baseline_run_id))
    ).scalar_one_or_none()
    if prior:
        run = Run.model_validate(prior)
        if run.config != config:
            raise ValueError("IMMUTABLE_BASELINE_CONFIGURATION")
        return run
    p = project(conn, config.project_id)
    candidate = onboarding.get_candidate(conn, p.candidate_id)
    if not p.broker_binding.ready() or (config.symbol, config.timeframe) != (
        p.broker_binding.broker_symbol,
        p.broker_binding.timeframe,
    ):
        raise ValueError("BLOCKED_SYMBOL")
    if candidate.artifact_id is None or candidate.artifact_sha256 is None:
        raise ValueError("NOT_READY")
    run = Run(
        config=config,
        candidate_id=candidate.candidate_id,
        artifact_id=candidate.artifact_id,
        ea_sha256=candidate.artifact_sha256,
        input_sha256=hashlib.sha256(config.set_text.encode()).hexdigest()
        if config.set_text is not None
        else None,
        declared_license_status=candidate.license_status,
        declared_tester_access=candidate.tester_access_status,
        created_at=datetime.now(UTC),
    )
    conn.execute(
        insert(runs).values(
            id=str(config.baseline_run_id),
            project_id=str(config.project_id),
            body=run.model_dump(mode="json"),
        )
    )
    return run


def advance(conn: Connection, run_id: UUID, target: State, **changes: Any) -> Run:
    run = get(conn, run_id, lock=True)
    transition(run.status, target)
    body = run.model_dump()
    body.update(changes, status=target, history=(*run.history, target))
    if target == State.PREPARING:
        body["started_at"] = datetime.now(UTC)
    if target not in {State.QUEUED, State.PREPARING, State.RUNNING, State.PARSING}:
        body["completed_at"] = datetime.now(UTC)
    updated = Run.model_validate(body)
    conn.execute(
        update(runs).where(runs.c.id == str(run_id)).values(body=updated.model_dump(mode="json"))
    )
    return updated


def result(conn: Connection, run_id: UUID) -> Result | None:
    body = conn.execute(
        select(results.c.body).where(results.c.id == str(run_id))
    ).scalar_one_or_none()
    return Result.model_validate(body) if body else None


def list_runs(conn: Connection, project_id: UUID) -> list[dict[str, Any]]:
    return list(
        conn.execute(
            select(runs.c.body)
            .where(runs.c.project_id == str(project_id))
            .order_by(runs.c.id)
            .limit(100)
        ).scalars()
    )
