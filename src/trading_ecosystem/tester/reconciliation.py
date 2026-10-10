"""Append-only offline assessments; no SDK, service, database writes or run transitions."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from trading_ecosystem.tester import evidence
from trading_ecosystem.tester.adapter import observed_failure
from trading_ecosystem.tester.contracts import Run, State
from trading_ecosystem.tester.execution_plan import CandidateExecutionPlan
from trading_ecosystem.tester.parser import parse
from trading_ecosystem.tester.tick_evidence import Coverage, extract


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def assess(
    root: Path,
    run: Run,
    expected_manifest: str,
    expected_raw_report: str,
    *,
    previous_assessment_identity: str | None = None,
) -> dict[str, Any]:
    """Verify preserved inputs before parsing; return a derived record, never a BaselineResult row.

    The original run remains terminal. A successful offline parse is explicitly unpublished:
    publishing it requires a separate reconciliation-aware product contract, not a transition
    from a blocked execution to COMPLETE or an insertion masquerading as execution-time output.
    """
    if run.status != State.BLOCKED_REAL_TICKS_UNAVAILABLE or run.exit_code != 0:
        raise ValueError("RECONCILIATION_EXECUTION_NOT_ELIGIBLE")
    if root.is_symlink():
        raise ValueError("UNSAFE_RECONCILIATION_SOURCE")
    manifest = json.loads((root / "manifest.json").read_bytes())
    identity = manifest.pop("identity")
    if identity != expected_manifest or digest(manifest) != identity:
        raise ValueError("RECONCILIATION_MANIFEST_MISMATCH")
    if run.evidence_identity != identity or manifest["status"] != run.status.value:
        raise ValueError("RECONCILIATION_RUN_MISMATCH")
    for name, sha in manifest["files"].items():
        source = root / name
        if Path(name).name != name or source.is_symlink() or evidence.file_identity(source) != sha:
            raise ValueError("RECONCILIATION_SOURCE_CHANGED")
    required = {
        "configuration.json",
        "report.htm",
        "tester-sanitized.log",
        "execution-plan.json",
        "native-report-origin.json",
        "native-cleanup.json",
        "execution-strategy.json",
    }
    if not required <= manifest["files"].keys():
        raise ValueError("RECONCILIATION_PROVENANCE_INCOMPLETE")
    original = Run.model_validate_json((root / "configuration.json").read_bytes())
    if (
        original.config != run.config
        or original.candidate_id != run.candidate_id
        or original.ea_sha256 != run.ea_sha256
        or original.authorization_event_id != run.authorization_event_id
    ):
        raise ValueError("RECONCILIATION_RUN_MISMATCH")
    saved_plan = json.loads((root / "execution-plan.json").read_bytes())
    plan = CandidateExecutionPlan.model_validate(saved_plan["content"])
    if (
        plan.identity != saved_plan["identity"]
        or plan.baseline_run_id != run.config.baseline_run_id
        or plan.candidate_id != run.candidate_id
        or plan.artifact_sha256 != run.ea_sha256
        or plan.configuration_id != run.config.configuration_id
        or plan.project_id != run.config.project_id
    ):
        raise ValueError("RECONCILIATION_PLAN_MISMATCH")
    origin = json.loads((root / "native-report-origin.json").read_bytes())
    if origin["raw_sha256"] != expected_raw_report:
        raise ValueError("RECONCILIATION_RAW_IDENTITY_MISMATCH")
    processes = json.loads((root / "native-cleanup.json").read_bytes())["processes"]
    for role in ("terminal", "tester"):
        matched = [p for p in processes if p["role"] == role]
        if len(matched) != 1 or not matched[0]["identity_verified"] or matched[0]["exit_code"] != 0:
            raise ValueError("RECONCILIATION_NATIVE_LIFECYCLE_UNVERIFIED")
    raw = (root / "report.htm").read_bytes()
    log = (root / "tester-sanitized.log").read_text(encoding="utf-8-sig")
    ticks = extract(run.config.tester_model, log, raw)
    normalized = None
    assessment = ticks.classification.value
    diagnostic = "FULL_REAL_TICK_REQUIREMENT_NOT_SATISFIED"
    if ticks.classification == Coverage.VERIFIED:
        if observed_failure(log) is not None:
            assessment, diagnostic = "REPORT_EVIDENCE_INSUFFICIENT", "EXPLICIT_NATIVE_FAILURE"
        else:
            try:
                parsed = parse(
                    raw, run.config.baseline_run_id, run.config.project_id, run.candidate_id
                )
                meta, cfg = parsed.metadata, run.config
                reference = plan.expert_reference.removesuffix(".ex5")
                if (
                    meta["Expert"].removesuffix(".ex5")
                    not in {reference, reference.rsplit("\\", 1)[-1]}
                    or meta["Symbol"] != cfg.symbol
                    or meta["timeframe"] != cfg.timeframe
                    or meta["from_date"] != f"{cfg.from_date:%Y.%m.%d}"
                    or meta["to_date"] != f"{cfg.to_date:%Y.%m.%d}"
                    or meta["Leverage"] != f"1:{cfg.leverage}"
                    or meta["Currency"] not in {"UNAVAILABLE", cfg.currency}
                    or meta["Model"] not in {"UNAVAILABLE", "Every tick based on real ticks"}
                    or Decimal(str(parsed.metrics["initial_deposit"])) != cfg.initial_deposit
                ):
                    raise ValueError("REPORT_CONFIGURATION_MISMATCH")
                normalized = parsed.model_dump(mode="json")
                diagnostic = "OFFLINE_PARSED_NOT_PUBLISHED_IMMUTABLE_RUN"
            except (ValueError, ArithmeticError):
                assessment, diagnostic = (
                    "REPORT_EVIDENCE_INSUFFICIENT",
                    "OFFLINE_REPORT_VALIDATION_FAILED",
                )
    body = {
        "schema": "PHASE5B_OFFLINE_RECONCILIATION_V1",
        "previous_assessment_identity": previous_assessment_identity,
        "baseline_run_id": str(run.config.baseline_run_id),
        "execution_outcome": run.status.value,
        "reconciled_assessment": assessment,
        "diagnostic": diagnostic,
        "tick_evidence": ticks.model_dump(mode="json"),
        "source_run_identity": digest(run.model_dump(mode="json")),
        "source_manifest_identity": identity,
        "source_file_hashes": manifest["files"],
        "native_raw_report_identity": expected_raw_report,
        "native_raw_bytes_retained": False,
        "preserved_report_identity": hashlib.sha256(raw).hexdigest(),
        "execution_plan_identity": plan.identity,
        "configuration_identity": plan.configuration_identity,
        "normalization_provenance": "POST_RUN_OFFLINE_RECONCILIATION",
        "offline_normalization": normalized,
        "baseline_result_created": False,
        "new_execution_attempts": 0,
        "publication_requirement": "EXPLICIT_RECONCILIATION_RESULT_STORAGE_AND_UI_CONTRACT",
    }
    return {**body, "reconciliation_identity": digest(body)}


def persist(output: Path, assessment: dict[str, Any]) -> None:
    """Exclusive new namespace with independent readback; never append to a run manifest."""
    body = {k: v for k, v in assessment.items() if k != "reconciliation_identity"}
    if digest(body) != assessment["reconciliation_identity"]:
        raise ValueError("RECONCILIATION_IDENTITY_MISMATCH")
    output.mkdir(parents=True, exist_ok=False)
    evidence.write_json(output / "assessment.json", assessment)
    if json.loads((output / "assessment.json").read_bytes()) != assessment:
        raise ValueError("RECONCILIATION_READBACK_FAILED")
    evidence.finalize(output, assessment["reconciled_assessment"])
