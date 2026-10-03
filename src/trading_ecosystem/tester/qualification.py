"""Candidate qualification with no SDK, MT5 launch, copy, or database-write calls."""

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection

from trading_ecosystem.tester import readiness, store
from trading_ecosystem.tester.adapter import configuration_text
from trading_ecosystem.tester.contracts import Configuration
from trading_ecosystem.tester.environment import TerminalBinding, local_path, validate_binding
from trading_ecosystem.workbench import store as onboarding


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def environment_proof(pinned: TerminalBinding, root: Path) -> dict[str, Any]:
    validate_binding(pinned)
    root = local_path(root)
    manifest = json.loads((root / "files.json").read_bytes())
    if not {"assessment.json", "account-binding.json"} <= set(manifest):
        raise ValueError("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
    for name, expected in manifest.items():
        path = local_path(root / name)
        if (
            not path.is_relative_to(root)
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
    result = json.loads((root / "assessment.json").read_bytes())
    account = json.loads((root / "account-binding.json").read_bytes())
    if account.get("environment_classification") != "DEMO":
        raise ValueError("BLOCKED_TESTER_ACCOUNT_NOT_DEMO")
    if (
        result.get("schema") != "PHASE5B1E_ACCOUNT_PROBE_V1"
        or result.get("status") != "BOOTSTRAP_READY"
        or not result.get("probe_init_succeeded")
        or not result.get("first_tick_observed")
        or not result.get("cleanup_verified")
        or result.get("account_binding") != account
        or result.get("candidate_staged") is not False
        or result.get("baseline_result") is not False
        or result.get("terminal_binding_id") != str(pinned.terminal_binding_id)
        or result.get("terminal_sha256") != pinned.terminal_sha256
        or result.get("terminal_build") != pinned.terminal_build
        or account.get("terminal_binding_id") != str(pinned.terminal_binding_id)
        or account.get("server") != pinned.server
    ):
        raise ValueError("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
    return {
        "status": "BOOTSTRAP_READY_AS_OBSERVED",
        "terminal_binding": pinned.model_dump(mode="json"),
        "account_binding": account,
        "probe_id": result["probe_id"],
        "proof_sha256": manifest["assessment.json"],
        "revalidate_at_execution": True,
        "full_interval_real_ticks": "UNKNOWN",
    }


def ingestion(provenance: str) -> str:
    if provenance == "USER_SUPPLIED_AUTHORIZED":
        return "USER_SUPPLIED_EX5"
    if provenance == "MARKETPLACE_AUTHORIZED":
        return "AUTHORIZED_MT5_INSTALLED_EA"
    raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")


def render(config: Configuration, expert: str, server: str) -> str:
    # Only an exact installed relative path, never an absolute path or INI injection.
    if not re.fullmatch(r"(?:[A-Za-z0-9_ -]+\\)*[A-Za-z0-9_ .-]+\.ex5", expert):
        raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")
    if any(part.startswith(".") or ".." in part for part in expert.split("\\")):
        raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")
    value = config.baseline_run_id.hex
    text = configuration_text(config, value, value + ".htm", server)
    return text.replace(f"Expert={value}.ex5\n", f"Expert={expert}\n", 1)


def qualify(
    conn: Connection,
    artifacts: Path,
    project_id: UUID,
    candidate_id: UUID,
    configuration_id: UUID,
    pinned: TerminalBinding,
    proof_root: Path,
    output_root: Path,
    qualification_id: UUID | None = None,
    *,
    installed_profile: bool = False,
) -> dict[str, Any]:
    """Read persisted identities afresh; emit a bound proposal, never an execution capability."""
    result: dict[str, Any] = {
        "schema": "PHASE5B1F_QUALIFICATION_V1",
        "project_id": str(project_id),
        "candidate_id": str(candidate_id),
        "configuration_id": str(configuration_id),
        "authorization": "NOT_CHECKED",
        "artifact": "NOT_CHECKED",
        "ingestion_mode": "UNKNOWN",
        "research_environment": "NOT_CHECKED",
        "native_config_dry_run": "NOT_RENDERED",
        "execution_binding": None,
        "declared_license_status": "UNKNOWN",
        "declared_tester_access_status": "UNKNOWN",
        "observed_tester_access_status": "UNKNOWN",
        "actual_execution_result": "NOT_EXECUTED",
        "candidate_native_attempts": 0,
        "execution_available": False,
    }
    try:
        output_root = local_path(output_root)
        namespace = ".local/phase5_b1g" if installed_profile else ".local/phase5_b1f"
        if not output_root.is_relative_to(Path(namespace).resolve()):
            raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")
        subprocess.run(
            ["git", "check-ignore", "--quiet", str(output_root)],
            check=True,
            capture_output=True,
            timeout=10,
        )
        project = store.project(conn, project_id)
        if project.candidate_id != candidate_id or project.source_type != "EXTERNAL_EA":
            raise ValueError("BASELINE_CONFIGURATION_ARTIFACT_MISMATCH")
        candidate = onboarding.get_candidate(conn, candidate_id)
        if project.broker_binding.broker_name != pinned.broker_name:
            raise ValueError("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
        result.update(
            declared_license_status=candidate.license_status,
            declared_tester_access_status=candidate.tester_access_status,
        )
        events = readiness.history(conn, project_id)
        if not events:
            raise ValueError("BLOCKED_AUTHORIZATION_PROVENANCE")
        attestation = readiness.Attestation.model_validate(events[-1])
        if attestation.candidate_id != candidate_id or attestation.provenance in {
            "UNKNOWN",
            "PROHIBITED_OR_UNVERIFIED",
        }:
            raise ValueError("BLOCKED_AUTHORIZATION_PROVENANCE")
        result.update(
            authorization="VERIFIED_USER_ATTESTATION",
            authorization_event_id=str(attestation.event_id),
        )
        if candidate.artifact_id is None:
            raise ValueError("BLOCKED_ARTIFACT_IDENTITY_MISMATCH")
        artifact = onboarding.get_artifact(conn, candidate.artifact_id)
        if (
            artifact.role != "EA"
            or artifact.sha256 != candidate.artifact_sha256
            or not onboarding.verify_artifact(artifacts, artifact)
        ):
            raise ValueError("BLOCKED_ARTIFACT_IDENTITY_MISMATCH")
        result.update(
            artifact="VERIFIED",
            artifact_id=str(artifact.artifact_id),
            artifact_sha256=artifact.sha256,
        )
        result["prior_execution_observations"] = [
            {
                "baseline_run_id": row["config"]["baseline_run_id"],
                "observed_tester_status": row.get("observed_tester_status", "UNKNOWN"),
                "status": row["status"],
            }
            for row in store.list_runs(conn, project_id)
            if row["candidate_id"] == str(candidate_id) and row["ea_sha256"] == artifact.sha256
        ]
        if candidate.license_status == "NOT_AUTHORIZED":
            raise ValueError("BLOCKED_LICENSE")
        if candidate.tester_access_status == "UNAVAILABLE":
            raise ValueError("BLOCKED_TESTER_ACCESS")
        record = readiness.get_configuration(conn, configuration_id)
        spec = readiness.BaselineConfiguration.model_validate(record["specification"])
        if spec.project_id != project_id:
            raise ValueError("BASELINE_CONFIGURATION_MISMATCH")
        identity = qualification_id or uuid4()  # namespace only; never inserted as a BaselineRun
        cfg = spec.execution(identity)
        readiness.require_execution_contract(conn, cfg)
        result["baseline_configuration"] = record
        environment = environment_proof(pinned, proof_root)
        result["research_environment"] = environment
        mode = ingestion(attestation.provenance)
        result["ingestion_mode"] = mode
        if installed_profile:
            from trading_ecosystem.tester.installed_profile import installed_path, strategy

            result["schema"] = "PHASE5B1G_QUALIFICATION_V1"
            result["execution_strategy"] = strategy(mode)
        if mode == "AUTHORIZED_MT5_INSTALLED_EA":
            expert = "Market\\" + artifact.filename
            path = (
                installed_path(pinned, artifact.filename)
                if installed_profile
                else local_path(
                    pinned.terminal_data_root / "MQL5/Experts/Market" / artifact.filename
                )
            )
            if not path.is_relative_to(pinned.terminal_data_root / "MQL5/Experts/Market"):
                raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")
            if not path.is_file():
                raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")
            if path.stat().st_size != artifact.size or (
                hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256
            ):
                raise ValueError("BLOCKED_ARTIFACT_IDENTITY_MISMATCH")
            representation = "EXISTING_INSTALLED_FILE_REFERENCE_NO_COPY"
        else:
            expert = identity.hex + ".ex5"
            path = output_root / "terminal/MQL5/Experts" / expert
            representation = "PROPOSED_USER_SUPPLIED_STAGING_NOT_PERFORMED"
        native = render(cfg, expert, pinned.server)
        binding = {
            "qualification_id": str(identity),
            "project": project.model_dump(mode="json"),
            "candidate": candidate.model_dump(mode="json"),
            "artifact": artifact.model_dump(mode="json"),
            "authorization": attestation.model_dump(mode="json"),
            "baseline_configuration": record,
            "environment": environment,
            "ingestion_mode": mode,
            "expert_reference": expert,
            "expert_path": str(path),
            "runtime_representation": representation,
            "native_config_sha256": hashlib.sha256(native.encode()).hexdigest(),
            "report_path": str(
                (
                    pinned.terminal_data_root
                    if mode == "AUTHORIZED_MT5_INSTALLED_EA"
                    else output_root / "terminal"
                )
                / (identity.hex + ".htm")
            ),
            "evidence_root": str(output_root),
            "timeout_seconds": cfg.timeout_seconds,
            "lifecycle": "OWNED_PROCESS_TREE_FIXED_TIMEOUT_NO_RETRY_REQUIRED",
            "account_materialization": "REVALIDATE_AND_EPHEMERAL_IDENTIFIER_AT_EXECUTION_ONLY",
        }
        result.update(
            execution_binding={"identity": digest(binding), "content": binding},
            native_config=native,
            native_config_dry_run="RENDERED_NOT_EXECUTABLE_QUALIFICATION_ONLY",
            runtime_representation=representation,
        )
        # The frozen production adapter only copies an EX5 into an isolated portable runtime.
        # It cannot consume the verified same-profile account binding or reference Market in place.
        # Do not silently route protected material through that copy/upload path.
        result["adapter_limitation"] = (
            "INSTALLED_EA_REFERENCE_AND_VERIFIED_ACCOUNT_BINDING_NOT_SUPPORTED_BY_EXECUTION_ADAPTER"
            if mode == "AUTHORIZED_MT5_INSTALLED_EA"
            else "VERIFIED_ACCOUNT_BINDING_NOT_SUPPORTED_BY_PORTABLE_EXECUTION_ADAPTER"
        )
        result["status"] = "BLOCKED_CANDIDATE_INGESTION_MODEL"
        if installed_profile and mode == "AUTHORIZED_MT5_INSTALLED_EA":
            from trading_ecosystem.tester.installed_profile import InstalledProfileAdapter

            plan = InstalledProfileAdapter().dry_run(binding, pinned, proof_root)
            binding["installed_profile"] = plan
            result.update(
                installed_profile=plan,
                execution_binding={"identity": digest(binding), "content": binding},
                native_config_dry_run="VERIFIED_DRY_RUN_NO_LAUNCH",
                status="CANDIDATE_EXECUTION_READY",
                adapter_limitation=None,
            )
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        known = {
            "BLOCKED_AUTHORIZATION_PROVENANCE",
            "BLOCKED_ARTIFACT_IDENTITY_MISMATCH",
            "BLOCKED_CANDIDATE_INGESTION_MODEL",
            "BLOCKED_CANDIDATE_PROFILE_MISMATCH",
            "BLOCKED_TERMINAL_IDENTITY_MISMATCH",
            "BLOCKED_TESTER_ACCOUNT_NOT_DEMO",
            "BASELINE_CONFIGURATION_REQUIRED",
            "BASELINE_CONFIGURATION_IDENTITY_MISMATCH",
            "BASELINE_CONFIGURATION_MISMATCH",
            "BASELINE_CONFIGURATION_ARTIFACT_MISMATCH",
            "BLOCKED_LICENSE",
            "BLOCKED_TESTER_ACCESS",
            "BLOCKED_SYMBOL",
        }
        result["status"] = (
            str(error) if str(error) in known else "BLOCKED_CANDIDATE_INGESTION_MODEL"
        )
    return result


def verify_binding(record: dict[str, Any], current: dict[str, Any]) -> None:
    """A later caller must requalify from DB/files; a saved digest alone grants no permission."""
    if record.get("identity") != digest(record.get("content")) or record != current:
        raise ValueError("CANDIDATE_EXECUTION_BINDING_CHANGED")
