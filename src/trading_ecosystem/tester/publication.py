"""Additive, offline publication of verified reconciliation; never transitions a run."""

import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Column, Connection, ForeignKey, String, Table, select
from sqlalchemy.dialects.postgresql import JSONB, insert

from trading_ecosystem.tester import evidence, parser, reconciliation, store
from trading_ecosystem.tester.contracts import Result
from trading_ecosystem.tester.execution_plan import CandidateExecutionPlan
from trading_ecosystem.workbench import store as onboarding

publications = Table(
    "reconciled_results",
    onboarding.metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("workbench.baseline_runs.id"), nullable=False, unique=True),
    Column("body", JSONB, nullable=False),
)


def read(conn: Connection, run_id: UUID) -> dict[str, Any] | None:
    body = conn.execute(
        select(publications.c.body).where(publications.c.run_id == str(run_id))
    ).scalar_one_or_none()
    if body is None:
        return None
    record: dict[str, Any] = dict(body)
    content = {k: v for k, v in record.items() if k not in {"id", "identity"}}
    identity = reconciliation.digest(content)
    if record["identity"] != identity or record["id"] != str(uuid5(NAMESPACE_URL, identity)):
        raise ValueError("PUBLICATION_IDENTITY_MISMATCH")
    return record


def publish(conn: Connection, run_id: UUID, source: Path, assessment: Path) -> dict[str, Any]:
    """Revalidate immutable inputs, insert once, and compare independent persisted readback."""
    run = store.get(conn, run_id, lock=True)
    saved = json.loads(assessment.read_bytes())
    verified = reconciliation.assess(
        source,
        run,
        saved["source_manifest_identity"],
        saved["native_raw_report_identity"],
        previous_assessment_identity=saved["previous_assessment_identity"],
    )
    if saved != verified:
        raise ValueError("PUBLICATION_RECONCILIATION_MISMATCH")
    if (
        saved["reconciled_assessment"] != "REAL_TICK_COVERAGE_VERIFIED_100"
        or saved["offline_normalization"] is None
    ):
        raise ValueError("PUBLICATION_NOT_ELIGIBLE")
    result = Result.model_validate(saved["offline_normalization"])
    plan = CandidateExecutionPlan.model_validate(
        json.loads((source / "execution-plan.json").read_bytes())["content"]
    )
    metrics = dict(result.metrics)
    if metrics["total_trades"] == 0:
        for name in (
            "win_rate",
            "profit_factor",
            "expected_payoff",
            "average_profit_trade",
            "average_loss_trade",
            "average_holding_time",
        ):
            if name in metrics:
                metrics[name] = None
    content = {
        "schema": "RECONCILED_RESULT_PUBLICATION_V1",
        "state": "PUBLISHED",
        "provenance": "POST_RUN_RECONCILIATION",
        "baseline_run_id": str(run_id),
        "candidate_id": str(run.candidate_id),
        "project_id": str(run.config.project_id),
        "configuration_id": str(run.config.configuration_id),
        "configuration_identity": saved["configuration_identity"],
        "execution_plan_identity": saved["execution_plan_identity"],
        "execution_strategy": plan.execution_strategy,
        "execution_outcome": run.status.value,
        "reconciliation_status": saved["reconciled_assessment"],
        "reconciliation_identity": saved["reconciliation_identity"],
        "source_manifest_identity": saved["source_manifest_identity"],
        "native_source_identity": saved["native_raw_report_identity"],
        "native_source_verification": "MANIFEST_PROVENANCE_ONLY_ORIGINAL_BYTES_NOT_RETAINED",
        "stored_utf8_report_identity": saved["preserved_report_identity"],
        "parser_source_identity": evidence.file_identity(Path(parser.__file__)),
        "parsed_result_identity": result.result_identity,
        "metrics": metrics,
        "metadata": result.metadata,
        "zero_trade_ratio_policy": "UNDEFINED_RATES_AND_AVERAGES_ARE_NULL",
    }
    identity = reconciliation.digest(content)
    record = {**content, "identity": identity, "id": str(uuid5(NAMESPACE_URL, identity))}
    conn.execute(
        insert(publications)
        .values(id=record["id"], run_id=str(run_id), body=record)
        .on_conflict_do_nothing(index_elements=[publications.c.run_id])
    )
    actual = read(conn, run_id)
    if actual != record:
        raise ValueError("IMMUTABLE_PUBLICATION_CONFLICT")
    return record
