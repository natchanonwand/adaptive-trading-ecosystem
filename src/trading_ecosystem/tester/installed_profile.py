"""In-place Marketplace preparation. No launch, copy, SDK, or license-storage capability."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from trading_ecosystem.tester.environment import TerminalBinding, local_path
from trading_ecosystem.tester.research_account import ResearchAccountBinding


def strategy(mode: str) -> str:
    if mode == "AUTHORIZED_MT5_INSTALLED_EA":
        return "INSTALLED_PROFILE_REFERENCE"
    if mode == "USER_SUPPLIED_EX5":
        return "PORTABLE_ARTIFACT"
    raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")


def installed_path(pinned: TerminalBinding, filename: str) -> Path:
    # Only a persisted leaf filename under Experts/Market; never accept an external path.
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_ .-]*\.ex5", filename)
        or ".." in filename
        or filename.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL"}
    ):
        raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")
    try:
        profile = local_path(pinned.terminal_data_root)
        allowed = local_path(profile / "MQL5/Experts/Market")
        path = local_path(allowed / filename)
        if not path.is_relative_to(allowed) or not path.is_file():
            raise ValueError("BLOCKED_CANDIDATE_PROFILE_MISMATCH")
        return path
    except OSError:
        raise ValueError("BLOCKED_CANDIDATE_PROFILE_MISMATCH") from None


class InstalledProfileAdapter:
    """Prepare a bound dry-run from DB-qualified content; it is not permission to execute.

    The native reference is relative to MQL5/Experts. Build 6230 native-generated
    presets in the pinned profile use Market\\<filename>.ex5, including spaces.
    Common.Login must only be supplied after fresh account revalidation in a later
    authorized acceptance. No credentials or account database are consumed here.
    """

    def dry_run(
        self, binding: dict[str, Any], pinned: TerminalBinding, proof_root: Path
    ) -> dict[str, Any]:
        if (
            binding["ingestion_mode"] != "AUTHORIZED_MT5_INSTALLED_EA"
            or binding["authorization"]["provenance"] != "MARKETPLACE_AUTHORIZED"
            or binding["authorization"]["confirmed"] is not True
        ):
            raise ValueError("BLOCKED_AUTHORIZATION_PROVENANCE")
        env = binding["environment"]
        account = ResearchAccountBinding.model_validate(env["account_binding"])
        raw = (local_path(proof_root) / "assessment.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != env["proof_sha256"]:
            raise ValueError("BLOCKED_CANDIDATE_PROFILE_MISMATCH")
        assessment = json.loads(raw)
        # Historical observations must identify this exact data root and executable,
        # not just an account on the same server or a terminal with the same build.
        profile = local_path(pinned.terminal_data_root)
        observed_profiles = {
            row["message"]
            for row in assessment.get("observations", [])
            if row.get("component") == "Terminal" and row.get("source", "").startswith("logs/")
        }
        observed_terminals = [
            row
            for row in assessment.get("processes", [])
            if row.get("role") == "terminal" and row.get("identity_verified") is True
        ]
        if (
            env["terminal_binding"] != pinned.model_dump(mode="json")
            or env["account_binding"] != assessment.get("account_binding")
            or pinned.terminal_build != "6230"
            or account.terminal_binding_id != pinned.terminal_binding_id
            or account.server != pinned.server
            or not account.company.strip()
            or not re.fullmatch(r"[a-f0-9]{64}", account.account_fingerprint)
            or str(profile) not in observed_profiles
            or len(observed_terminals) != 1
            or observed_terminals[0].get("image") != str(pinned.terminal_executable)
            or observed_terminals[0].get("sha256") != pinned.terminal_sha256
        ):
            raise ValueError("BLOCKED_CANDIDATE_PROFILE_MISMATCH")
        artifact = binding["artifact"]
        candidate = binding["candidate"]
        path = installed_path(pinned, artifact["filename"])
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if (
            actual != artifact["sha256"]
            or actual != candidate["artifact_sha256"]
            or path.stat().st_size != artifact["size"]
        ):
            raise ValueError("BLOCKED_ARTIFACT_IDENTITY_MISMATCH")
        if (
            artifact["role"] != "EA"
            or candidate["artifact_id"] != artifact["artifact_id"]
            or binding["project"]["candidate_id"] != candidate["candidate_id"]
            or binding["authorization"]["candidate_id"] != candidate["candidate_id"]
            or binding["expert_reference"] != "Market\\" + artifact["filename"]
            or binding["expert_path"] != str(path)
        ):
            raise ValueError("BLOCKED_CANDIDATE_PROFILE_MISMATCH")
        params = binding["baseline_configuration"]["specification"]["parameters"]
        if params["set_text"] is not None or params["input_provenance"] != "TESTER_DEFAULTS":
            raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")
        # MT5 can implicitly read Expert_name.set when ExpertParameters is omitted.
        # Never delete/replace a user's preset or silently call those inputs defaults.
        presets = local_path(profile / "MQL5/Profiles/Tester")
        for relative in (path.stem + ".set", "Market/" + path.stem + ".set"):
            if local_path(presets / relative).exists():
                raise ValueError("BLOCKED_CANDIDATE_INGESTION_MODEL")
        return {
            "execution_strategy": "INSTALLED_PROFILE_REFERENCE",
            "candidate_id": candidate["candidate_id"],
            "candidate_display_name": candidate["product_name"],
            "persisted_sha256": artifact["sha256"],
            "installed_sha256": actual,
            "expert_reference": binding["expert_reference"],
            "profile_identity": hashlib.sha256(str(profile).encode()).hexdigest(),
            "terminal_binding_id": str(pinned.terminal_binding_id),
            "account_binding_id": str(account.account_binding_id),
            "profile_binding": "VERIFIED",
            "path_safety": "VERIFIED",
            "input_defaults": "NO_IMPLICIT_PRESET_PRESENT",
            "native_mode": "PINNED_INSTALLATION_MAIN_MODE",
            "portable": False,
            "binary_copy": False,
            "requires_fresh_account_revalidation": True,
            "native_launch_enabled": False,
        }


def public_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Whitelist projection: never expose native paths, account material, or full config."""
    plan = result.get("installed_profile", {})
    return {
        "configuration_id": result["configuration_id"],
        "status": result["status"],
        "authorization": result["authorization"],
        "artifact": result["artifact"],
        "execution_strategy": result.get("execution_strategy", "UNKNOWN"),
        "profile_binding": plan.get("profile_binding", "NOT_VERIFIED"),
        "research_environment": ("READY_AS_OBSERVED" if plan else "NOT_VERIFIED"),
        "baseline_configuration": (
            "READY" if result.get("baseline_configuration") else "NOT_VERIFIED"
        ),
        "native_config_dry_run": result["native_config_dry_run"],
        "license": result["declared_license_status"],
        "tester_access": result["declared_tester_access_status"],
        "observed_tester_access": result["observed_tester_access_status"],
        "execution_available": False,
    }
