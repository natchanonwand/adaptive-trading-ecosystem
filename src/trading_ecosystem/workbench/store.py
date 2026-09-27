"""PostgreSQL metadata and content-addressed opaque artifact storage."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, Connection, MetaData, String, Table, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB, insert

from trading_ecosystem.workbench.contracts import (
    CATALOG,
    Artifact,
    Candidate,
    CreateProject,
    Project,
    SourceType,
    Status,
    readiness,
    transition,
)

metadata = MetaData(schema="workbench")
artifacts = Table(
    "artifacts",
    metadata,
    Column("id", String, primary_key=True),
    Column("sha256", String, nullable=False),
    Column("role", String, nullable=False),
    Column("body", JSONB, nullable=False),
    UniqueConstraint("sha256", "role"),
)
candidates = Table(
    "candidates",
    metadata,
    Column("id", String, primary_key=True),
    Column("body", JSONB, nullable=False),
)
projects = Table(
    "projects",
    metadata,
    Column("id", String, primary_key=True),
    Column("request_hash", String, nullable=False),
    Column("body", JSONB, nullable=False),
)
MAX_BYTES = 16 * 1024 * 1024


def artifact_path(root: Path, artifact: Artifact) -> Path:
    return root / (artifact.sha256 + (".ex5" if artifact.role == "EA" else ".pdf"))


def get_artifact(conn: Connection, artifact_id: UUID) -> Artifact:
    body = conn.execute(
        select(artifacts.c.body).where(artifacts.c.id == str(artifact_id))
    ).scalar_one_or_none()
    if body is None:
        raise ValueError("ARTIFACT_NOT_FOUND")
    return Artifact.model_validate(body)


def verify_artifact(root: Path, artifact: Artifact) -> bool:
    path = artifact_path(root, artifact)
    return (
        path.is_file()
        and not path.is_symlink()
        and path.stat().st_size == artifact.size
        and hashlib.sha256(path.read_bytes()).hexdigest() == artifact.sha256
    )


def register_artifact(
    conn: Connection, root: Path, filename: str, role: str, data: bytes
) -> Artifact:
    suffix = {"EA": ".ex5", "MANUAL": ".pdf"}.get(role)
    if (
        suffix is None
        or not filename.lower().endswith(suffix)
        or len(filename) > 200
        or any(c in filename for c in "/\\:\x00")
        or filename.startswith(".")
        or any(ord(c) < 32 for c in filename)
        or not 0 < len(data) <= MAX_BYTES
    ):
        raise ValueError("INVALID_ARTIFACT")
    artifact = Artifact(
        artifact_id=uuid4(),
        role=role,
        filename=filename,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        uploaded_at=datetime.now(UTC),
    )
    root.mkdir(parents=True, exist_ok=True)
    path = artifact_path(root, artifact)
    try:
        with path.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError:
        if not verify_artifact(root, artifact):
            raise ValueError("ARTIFACT_INTEGRITY_FAILURE") from None
    conn.execute(
        insert(artifacts)
        .values(
            id=str(artifact.artifact_id),
            sha256=artifact.sha256,
            role=role,
            body=artifact.model_dump(mode="json"),
        )
        .on_conflict_do_nothing(index_elements=["sha256", "role"])
    )
    body = conn.execute(
        select(artifacts.c.body).where(
            artifacts.c.sha256 == artifact.sha256, artifacts.c.role == role
        )
    ).scalar_one()
    return Artifact.model_validate(body)


def create_project(conn: Connection, root: Path, request: CreateProject) -> Project:
    if request.source_type != SourceType.EXTERNAL_EA:
        raise ValueError("SOURCE_TYPE_COMING_SOON")
    candidate_input = request.candidate
    if candidate_input.catalog_id is not None and candidate_input.catalog_id not in {
        c["catalog_id"] for c in CATALOG
    }:
        raise ValueError("UNKNOWN_CATALOG_ENTRY")
    request_hash = hashlib.sha256(
        json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    # Transaction-scoped lock serializes retries of the same project identity.
    from sqlalchemy import text

    conn.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": request.project_id.int % (2**63 - 1)}
    )
    prior = (
        conn.execute(select(projects).where(projects.c.id == str(request.project_id)))
        .mappings()
        .first()
    )
    if prior:
        if prior["request_hash"] != request_hash:
            raise ValueError("PROJECT_ID_CONFLICT")
        return Project.model_validate(prior["body"])
    fields: dict[str, Any] = {}
    for field, artifact_id, role in (
        ("artifact", candidate_input.artifact_id, "EA"),
        ("manual", candidate_input.manual_id, "MANUAL"),
    ):
        if artifact_id:
            artifact = get_artifact(conn, artifact_id)
            if artifact.role != role or not verify_artifact(root, artifact):
                raise ValueError("ARTIFACT_INTEGRITY_FAILURE")
            fields.update(
                {
                    field + "_filename": artifact.filename,
                    field + "_sha256": artifact.sha256,
                    field + "_size": artifact.size,
                }
            )
    binding = request.broker_binding
    candidate = Candidate(
        **candidate_input.model_dump(),
        candidate_id=uuid4(),
        expected_asset=binding.canonical_asset,
        expected_symbol=binding.broker_symbol,
        expected_timeframe=binding.timeframe,
        **fields,
    )
    status = readiness(candidate_input, binding)
    history = [Status.DRAFT]
    if status != Status.DRAFT:
        history.append(transition(history[-1], Status.CANDIDATE_REGISTERED))
        history.append(transition(history[-1], status))
    now = datetime.now(UTC)
    project = Project(
        project_id=request.project_id,
        project_name=request.project_name,
        source_type=request.source_type,
        candidate_id=candidate.candidate_id,
        broker_binding=binding,
        status=status,
        status_history=tuple(history),
        created_at=now,
        updated_at=now,
    )
    conn.execute(
        insert(candidates).values(
            id=str(candidate.candidate_id), body=candidate.model_dump(mode="json")
        )
    )
    conn.execute(
        insert(projects).values(
            id=str(project.project_id),
            request_hash=request_hash,
            body=project.model_dump(mode="json"),
        )
    )
    return project


def get_candidate(conn: Connection, candidate_id: UUID) -> Candidate:
    body = conn.execute(
        select(candidates.c.body).where(candidates.c.id == str(candidate_id))
    ).scalar_one_or_none()
    if body is None:
        raise ValueError("CANDIDATE_NOT_FOUND")
    return Candidate.model_validate(body)


def detail(conn: Connection, root: Path, project_id: UUID) -> dict[str, Any]:
    body = conn.execute(
        select(projects.c.body).where(projects.c.id == str(project_id))
    ).scalar_one_or_none()
    if body is None:
        raise ValueError("PROJECT_NOT_FOUND")
    project = Project.model_validate(body)
    candidate = get_candidate(conn, project.candidate_id)
    verification = {}
    for name, artifact_id in (("ea", candidate.artifact_id), ("manual", candidate.manual_id)):
        verification[name] = (
            ("VERIFIED" if verify_artifact(root, get_artifact(conn, artifact_id)) else "FAILED")
            if artifact_id
            else "NOT_PROVIDED"
        )
    # Readiness is a current projection, not a rewrite of historical declarations/history.
    current_status = readiness(candidate, project.broker_binding)
    if current_status == Status.BASELINE_READY and (
        verification["ea"] != "VERIFIED" or verification["manual"] == "FAILED"
    ):
        current_status = Status.DRAFT
    return dict(
        project={**body, "status": current_status.value},
        candidate=candidate.model_dump(mode="json"),
        verification=verification,
        baseline_status="READY"
        if current_status == Status.BASELINE_READY
        and verification["ea"] == "VERIFIED"
        and verification["manual"] != "FAILED"
        else "NOT_READY",
        execution_available=False,
    )


def list_projects(
    conn: Connection,
    offset: int = 0,
    root: Path = Path(".local/artifacts/research_projects"),
) -> dict[str, Any]:
    rows = list(
        conn.execute(
            select(projects.c.body).order_by(projects.c.id).offset(offset).limit(51)
        ).scalars()
    )
    items = []
    for row in rows[:50]:
        candidate = get_candidate(conn, UUID(row["candidate_id"]))
        current = detail(conn, root, UUID(row["project_id"]))
        items.append({**current["project"], "product_name": candidate.product_name})
    return dict(items=items, next_offset=offset + 50 if len(rows) > 50 else None)
