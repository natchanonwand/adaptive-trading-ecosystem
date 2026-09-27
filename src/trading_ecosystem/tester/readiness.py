"""Explicit user attestations and immutable input specifications; no execution I/O."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import model_validator
from sqlalchemy import Column, Connection, ForeignKey, String, Table, select, text
from sqlalchemy.dialects.postgresql import JSONB

from trading_ecosystem.domain.primitives import FrozenModel, UtcTimestamp
from trading_ecosystem.tester import store
from trading_ecosystem.tester.contracts import Configuration
from trading_ecosystem.workbench import store as onboarding
from trading_ecosystem.workbench.contracts import Text

Provenance = Literal[
    "UNKNOWN",
    "USER_SUPPLIED_AUTHORIZED",
    "FREE_VENDOR_DISTRIBUTION",
    "MARKETPLACE_AUTHORIZED",
    "VENDOR_TRIAL_AUTHORIZED",
    "OTHER_EXPLICIT_AUTHORIZATION",
    "PROHIBITED_OR_UNVERIFIED",
]


class Authorization(FrozenModel):
    event_id: UUID
    previous_event_id: UUID | None = None
    provenance: Provenance
    source_reference: Text
    source_label: Text
    authorization_basis: Text
    confirmed: Literal[True]

    @model_validator(mode="after")
    def supported(self) -> "Authorization":
        if self.provenance not in {"UNKNOWN", "PROHIBITED_OR_UNVERIFIED"} and "UNKNOWN" in (
            self.source_reference,
            self.source_label,
            self.authorization_basis,
        ):
            raise ValueError("EXPLICIT_SOURCE_AND_AUTHORIZATION_BASIS_REQUIRED")
        return self


class Attestation(Authorization):
    candidate_id: UUID
    revision: int
    authorization_attested_at: UtcTimestamp
    attestation_type: Literal["USER_ATTESTED_NOT_VENDOR_VERIFIED"] = (
        "USER_ATTESTED_NOT_VENDOR_VERIFIED"
    )


class BaselineConfiguration(FrozenModel):
    configuration_id: UUID
    project_id: UUID
    parameters: dict[str, Any]
    confirmed: Literal[True]

    @model_validator(mode="after")
    def validated(self) -> "BaselineConfiguration":
        if set(self.parameters) & {"baseline_run_id", "project_id", "configuration_id"}:
            raise ValueError("IDENTITY_IS_NOT_AN_INPUT_PARAMETER")
        parsed = self.execution(UUID(int=0))
        if parsed.input_provenance == "USER_SET":
            raise ValueError("USE_USER_SUPPLIED_SET")
        return self

    def execution(self, run_id: UUID) -> Configuration:
        return Configuration.model_validate(
            dict(
                **self.parameters,
                baseline_run_id=run_id,
                project_id=self.project_id,
                configuration_id=self.configuration_id,
            )
        )


authorizations = Table(
    "candidate_authorizations",
    onboarding.metadata,
    Column("id", String, primary_key=True),
    Column("candidate_id", String, ForeignKey("workbench.candidates.id"), nullable=False),
    Column("body", JSONB, nullable=False),
)
configurations = Table(
    "baseline_configurations",
    onboarding.metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, ForeignKey("workbench.projects.id"), nullable=False),
    Column("body", JSONB, nullable=False),
)


def history(conn: Connection, project_id: UUID) -> list[dict[str, Any]]:
    p = store.project(conn, project_id)
    return list(
        conn.execute(
            select(authorizations.c.body)
            .where(authorizations.c.candidate_id == str(p.candidate_id))
            .order_by(authorizations.c.body["revision"].as_integer())
        ).scalars()
    )


def attest(conn: Connection, project_id: UUID, value: Authorization) -> Attestation:
    p = store.project(conn, project_id)
    conn.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": p.candidate_id.int % (2**63 - 1)}
    )
    prior = conn.execute(
        select(authorizations.c.body).where(authorizations.c.id == str(value.event_id))
    ).scalar_one_or_none()
    if prior:
        record = Attestation.model_validate(prior)
        if (
            record.candidate_id != p.candidate_id
            or Authorization.model_validate({k: prior[k] for k in Authorization.model_fields})
            != value
        ):
            raise ValueError("IMMUTABLE_AUTHORIZATION_EVENT")
        return record
    events = history(conn, project_id)
    latest = UUID(events[-1]["event_id"]) if events else None
    if latest != value.previous_event_id:
        raise ValueError("STALE_AUTHORIZATION_REVIEW")
    record = Attestation(
        **value.model_dump(),
        candidate_id=p.candidate_id,
        revision=len(events) + 1,
        authorization_attested_at=datetime.now(UTC),
    )
    conn.execute(
        authorizations.insert().values(
            id=str(record.event_id),
            candidate_id=str(p.candidate_id),
            body=record.model_dump(mode="json"),
        )
    )
    return record


def get_configuration(conn: Connection, config_id: UUID) -> dict[str, Any]:
    body = conn.execute(
        select(configurations.c.body).where(configurations.c.id == str(config_id))
    ).scalar_one_or_none()
    if body is None:
        raise ValueError("BASELINE_CONFIGURATION_REQUIRED")
    expected = body["configuration_identity"]
    content = {k: v for k, v in body.items() if k != "configuration_identity"}
    if (
        hashlib.sha256(
            json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        != expected
    ):
        raise ValueError("BASELINE_CONFIGURATION_IDENTITY_MISMATCH")
    return dict(body)


def list_configurations(conn: Connection, project_id: UUID) -> list[dict[str, Any]]:
    store.project(conn, project_id)
    return list(
        conn.execute(
            select(configurations.c.body)
            .where(configurations.c.project_id == str(project_id))
            .order_by(configurations.c.id)
        ).scalars()
    )


def save_configuration(
    conn: Connection, root: Path, value: BaselineConfiguration
) -> dict[str, Any]:
    cfg = value.execution(UUID(int=0))
    p = store.project(conn, value.project_id)
    candidate = onboarding.get_candidate(conn, p.candidate_id)
    if not p.broker_binding.ready() or (cfg.symbol, cfg.timeframe) != (
        p.broker_binding.broker_symbol,
        p.broker_binding.timeframe,
    ):
        raise ValueError("BLOCKED_SYMBOL")
    if candidate.artifact_id is None or not onboarding.verify_artifact(
        root, onboarding.get_artifact(conn, candidate.artifact_id)
    ):
        raise ValueError("BLOCKED_ARTIFACT_IDENTITY_MISMATCH")
    conn.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": value.configuration_id.int % (2**63 - 1)},
    )
    payload = value.model_dump(mode="json")
    payload["parameters"] = cfg.model_dump(
        mode="json", exclude={"baseline_run_id", "project_id", "configuration_id"}
    )
    prior = conn.execute(
        select(configurations.c.body).where(configurations.c.id == str(value.configuration_id))
    ).scalar_one_or_none()
    if prior:
        if prior["specification"] != payload:
            raise ValueError("IMMUTABLE_BASELINE_CONFIGURATION")
        return dict(prior)
    body = dict(
        specification=payload,
        candidate_id=str(p.candidate_id),
        artifact_id=str(candidate.artifact_id),
        ea_sha256=candidate.artifact_sha256,
        created_at=datetime.now(UTC).isoformat(),
        exact_inputs_known=cfg.set_text is not None,
        input_limitation=None
        if cfg.set_text is not None
        else "EXACT_DEFAULT_INPUTS_UNAVAILABLE_BEFORE_INITIALIZATION",
    )
    body["configuration_identity"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    conn.execute(
        configurations.insert().values(
            id=str(value.configuration_id), project_id=str(value.project_id), body=body
        )
    )
    return body


def require_execution_contract(conn: Connection, config: Configuration) -> None:
    events = history(conn, config.project_id)
    if not events or events[-1]["provenance"] in {"UNKNOWN", "PROHIBITED_OR_UNVERIFIED"}:
        raise ValueError("BLOCKED_AUTHORIZATION_PROVENANCE")
    if config.configuration_id is None:
        raise ValueError("BASELINE_CONFIGURATION_REQUIRED")
    record = get_configuration(conn, config.configuration_id)
    spec = BaselineConfiguration.model_validate(record["specification"])
    if spec.execution(config.baseline_run_id) != config:
        raise ValueError("BASELINE_CONFIGURATION_MISMATCH")
    candidate = onboarding.get_candidate(conn, store.project(conn, config.project_id).candidate_id)
    binding = store.project(conn, config.project_id).broker_binding
    if not binding.ready() or (config.symbol, config.timeframe) != (
        binding.broker_symbol,
        binding.timeframe,
    ):
        raise ValueError("BLOCKED_SYMBOL")
    if (str(candidate.candidate_id), str(candidate.artifact_id), candidate.artifact_sha256) != (
        record["candidate_id"],
        record["artifact_id"],
        record["ea_sha256"],
    ):
        raise ValueError("BASELINE_CONFIGURATION_ARTIFACT_MISMATCH")


def detail(conn: Connection, root: Path, project_id: UUID) -> dict[str, Any]:
    result = onboarding.detail(conn, root, project_id)
    events = history(conn, project_id)
    configs = list_configurations(conn, project_id)
    reasons = []
    if not events or events[-1]["provenance"] in {"UNKNOWN", "PROHIBITED_OR_UNVERIFIED"}:
        reasons.append("BLOCKED_AUTHORIZATION_PROVENANCE")
    if result["baseline_status"] != "READY":
        reasons.append(result["project"]["status"])
    valid_configs = []
    for record in configs:
        try:
            spec = BaselineConfiguration.model_validate(record["specification"])
            # Check the immutable identity independently of current authorization status.
            get_configuration(conn, spec.configuration_id)
            cfg = spec.execution(UUID(int=0))
            binding = result["project"]["broker_binding"]
            if (cfg.symbol, cfg.timeframe) == (binding["broker_symbol"], binding["timeframe"]):
                valid_configs.append(record)
        except ValueError:
            pass
    if not valid_configs:
        reasons.append("BASELINE_CONFIGURATION_REQUIRED")
    result.update(
        readiness_enabled=True,
        baseline_enabled=True,
        authorization=events[-1] if events else {"provenance": "UNKNOWN"},
        authorization_history=events,
        configurations=configs,
        acceptance_readiness={"status": "NOT_READY" if reasons else "READY", "reasons": reasons},
    )
    return result
