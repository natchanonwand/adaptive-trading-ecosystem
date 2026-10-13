"""Reviewed, exact campaign capabilities. Authorization never starts a worker."""

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import Connection

from trading_ecosystem.experiments import campaign_store as ledger
from trading_ecosystem.experiments import campaigns
from trading_ecosystem.experiments.contracts import digest
from trading_ecosystem.experiments.reference_contract import ReferenceDefinition, parse_definition
from trading_ecosystem.tester import readiness
from trading_ecosystem.tester.adapter import Blocked, load_environment
from trading_ecosystem.workbench import store as onboarding


def capability(body: dict[str, Any], environment: dict[str, Any]) -> dict[str, Any]:
    d = parse_definition(body["definition"])
    if not isinstance(d, ReferenceDefinition):
        raise ValueError("CAMPAIGN_AUTHORIZATION_PROTOCOL_UNQUALIFIED")
    if (
        body["plan"]["candidates"] != campaigns.generate(d)
        or body["plan"]["bindings"] != campaigns.bindings(d)
        or body["plan_identity"] != digest(body["plan"])
    ):
        raise ValueError("CAMPAIGN_PLAN_CHANGED")
    return {
        "protocol": "EXPLICIT_CAMPAIGN_AUTHORIZATION_V1",
        "campaign_id": body["id"],
        "campaign_identity": body["plan_identity"],
        "bindings": campaigns.bindings(d),
        "source_sha256": d.source_sha256,
        "canonical_ex5_sha256": d.canonical_ex5_sha256,
        "build_identity": d.build_identity,
        "environment": environment,
        "allowed_stages": ["DEVELOPMENT", "VALIDATION"],
        "denied_stages": ["LOCKED_OOS"],
        "stage_budgets": {"DEVELOPMENT": 9, "VALIDATION": 2},
        "selection": "TOP_2_NET_PROFIT_DESC_IDENTITY_ASC_ACTIVITY_GE_10",
    }


def verify_capability(body: dict[str, Any], environment: dict[str, Any], stage: str) -> None:
    if stage not in {"DEVELOPMENT", "VALIDATION"}:
        raise ValueError("LOCKED_OOS_DENIED")
    expected = capability(body, environment)
    grant = body.get("execution_authorization")
    if not grant or grant != {
        "state": "AUTHORIZED",
        "content": expected,
        "identity": digest(expected),
    }:
        raise ValueError("CAMPAIGN_NOT_AUTHORIZED_OR_BINDING_CHANGED")


def identity_context(
    conn: Connection, body: dict[str, Any], artifacts: Path, root: Path
) -> dict[str, Any]:
    d = parse_definition(body["definition"])
    if not isinstance(d, ReferenceDefinition):
        raise ValueError("CAMPAIGN_AUTHORIZATION_PROTOCOL_UNQUALIFIED")
    candidate = onboarding.get_candidate(conn, d.candidate_id)
    if candidate.artifact_id is None:
        raise ValueError("CANONICAL_ARTIFACT_MISSING")
    artifact = onboarding.get_artifact(conn, candidate.artifact_id)
    if artifact.sha256 != d.canonical_ex5_sha256 or not onboarding.verify_artifact(
        artifacts, artifact
    ):
        raise ValueError("CANONICAL_ARTIFACT_CHANGED")
    source = Path(__file__).with_name("ReferenceEmaCrossM5.mq5")
    if hashlib.sha256(source.read_bytes()).hexdigest() != d.source_sha256:
        raise ValueError("PROJECT_SOURCE_CHANGED")
    events = readiness.history(conn, d.project_id)
    if not events or events[-1]["provenance"] != "PROJECT_SOURCE":
        raise ValueError("PROJECT_SOURCE_AUTHORIZATION_REQUIRED")
    build = json.loads((root.parent / "phase5_c2b/canonical-build.json").read_bytes())
    if digest(build["content"]) != d.build_identity or build["identity"] != d.build_identity:
        raise ValueError("BUILD_PROVENANCE_CHANGED")
    if (build["content"]["source_sha256"], build["content"]["canonical_ex5_sha256"]) != (
        d.source_sha256,
        d.canonical_ex5_sha256,
    ):
        raise ValueError("BUILD_ARTIFACT_BINDING_CHANGED")
    binding = json.loads((root / "terminal-binding.json").read_bytes())
    return {
        "classification": "DEMO_RESEARCH_TESTER",
        "terminal_binding": binding,
        "candidate_authorization_identity": digest(events[-1]),
    }


def review(conn: Connection, key: UUID, artifacts: Path, root: Path) -> dict[str, Any]:
    body = ledger.read(conn, key)
    try:
        environment = identity_context(conn, body, artifacts, root)
        content = capability(body, environment)
    except (ValueError, OSError, KeyError):
        return {
            "state": "NOT_AUTHORIZED",
            "start_eligible": False,
            "blocker": "CAMPAIGN_IDENTITY_OR_PROVENANCE_UNVERIFIED",
        }
    # Existing portable pathway deliberately fails closed until native profile qualification.
    blocker = None
    try:
        load_environment(root / "environment.json")
    except Blocked as exc:
        blocker = exc.status.value
    except (ValueError, OSError):
        blocker = "RESEARCH_ENVIRONMENT_UNAVAILABLE"
    authorized = body.get("execution_authorization") == {
        "state": "AUTHORIZED",
        "content": content,
        "identity": digest(content),
    }
    return {
        "state": "AUTHORIZED" if authorized else "NOT_AUTHORIZED",
        "review_identity": digest(content),
        "content": content,
        "start_eligible": authorized and blocker is None,
        "authorization_eligible": blocker is None,
        "blocker": blocker,
    }


def authorize(
    conn: Connection,
    key: UUID,
    artifacts: Path,
    root: Path,
    expected_review: str,
    confirmed: bool,
) -> dict[str, Any]:
    body = ledger.read(conn, key, True)
    value = review(conn, key, artifacts, root)
    if not confirmed or value.get("review_identity") != expected_review:
        raise ValueError("EXPLICIT_EXACT_REVIEW_REQUIRED")
    if not value.get("authorization_eligible"):
        raise ValueError("RESEARCH_ENVIRONMENT_NOT_READY")
    grant = {"state": "AUTHORIZED", "content": value["content"], "identity": expected_review}
    if body.get("execution_authorization") not in (None, grant):
        raise ValueError("IMMUTABLE_AUTHORIZATION_CONFLICT")
    if body.get("execution_authorization") is None:
        body["execution_authorization"] = grant
        ledger.event(body, "EXPLICIT_EXECUTION_AUTHORIZATION", identity=expected_review)
        ledger.persist(conn, body)
    return value | {"state": "AUTHORIZED", "start_eligible": True}


def require(conn: Connection, key: UUID, artifacts: Path, root: Path, stage: str) -> None:
    body = ledger.read(conn, key)
    environment = identity_context(conn, body, artifacts, root)
    verify_capability(body, environment, stage)
    if not review(conn, key, artifacts, root)["start_eligible"]:
        raise ValueError("RESEARCH_ENVIRONMENT_NOT_READY")
