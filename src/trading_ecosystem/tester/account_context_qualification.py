"""Persisted MAIN-MODE readiness and one separate reference qualification lifecycle."""

import hashlib
import json
import os
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

from trading_ecosystem.tester.account_probe import (
    capture_logs,
    log_positions,
    remove_probe_reports,
    restrict_runtime,
)
from trading_ecosystem.tester.adapter import configuration_text
from trading_ecosystem.tester.contracts import Configuration
from trading_ecosystem.tester.environment import (
    TerminalBinding,
    file_identity,
    local_path,
    validate_binding,
    validate_config,
)
from trading_ecosystem.tester.evidence import finalize, write_json
from trading_ecosystem.tester.handshake import Observer, classify, journal
from trading_ecosystem.tester.portable_qualification import (
    ARTIFACT,
    CANDIDATE,
    INPUTS,
    validate_artifact,
)
from trading_ecosystem.tester.process import execute
from trading_ecosystem.tester.qualification import digest, environment_proof
from trading_ecosystem.tester.research_account import AccountBlocked, discover, running_terminals


def persisted_binding(pinned: TerminalBinding, proof: dict[str, Any]) -> dict[str, Any]:
    account = proof["account_binding"]
    if (
        proof["terminal_binding"] != pinned.model_dump(mode="json")
        or account["environment_classification"] != "DEMO"
        or account["server"] != "Exness-MT5Trial14"
        or account["company"] != "Exness Technologies Ltd"
        or pinned.terminal_build != "6230"
        or account["terminal_binding_id"] != str(pinned.terminal_binding_id)
    ):
        raise ValueError("BLOCKED_ACCOUNT_ATTESTATION_MISMATCH")
    content = {
        "artifact_strategy": "PORTABLE_ARTIFACT",
        "account_context_strategy": "AUTHENTICATED_PROFILE_REFERENCE",
        "terminal_mode": "MAIN_MODE",
        "terminal_sha256": pinned.terminal_sha256,
        "terminal_build": pinned.terminal_build,
        "terminal_path": str(local_path(pinned.terminal_executable)),
        "profile_path": str(local_path(pinned.terminal_data_root)),
        "account_binding_id": account["account_binding_id"],
        "account_fingerprint": account["account_fingerprint"],
        "account_type": "DEMO",
        "company": account["company"],
        "server": account["server"],
        "candidate_id": CANDIDATE,
        "artifact_sha256": ARTIFACT,
        "purpose": "RESEARCH",
        "state": "PERSISTED_ACCOUNT_CONTEXT_READY_FOR_RUNTIME_PROBE",
        "selector": "MT5_PERSISTED_LAST_ACCOUNT_NO_EXPLICIT_LOGIN",
    }
    return {"identity": digest(content), "content": content}


def ownership_ready() -> None:
    # Conservatively reject any running terminal, including an ambiguous executable path.
    if running_terminals():
        raise ValueError("BLOCKED_PROFILE_IN_USE")


def offline(pinned: TerminalBinding, artifact: Path) -> dict[str, Any]:
    ownership_ready()
    validate_binding(pinned)
    if file_identity(pinned.terminal_executable)["build"] != "6230":
        raise ValueError("BLOCKED_TERMINAL_BUILD_MISMATCH")
    validate_artifact(
        (Path(__file__).parent.parent / "experiments/ReferenceEmaCrossM5.mq5").resolve(),
        artifact,
    )
    account_store = local_path(pinned.terminal_data_root / "config/accounts.dat")
    # Metadata only: never read, hash, decrypt, parse or copy this secret-bearing store.
    if not account_store.is_file() or account_store.stat().st_size == 0:
        raise ValueError("BLOCKED_ACCOUNT_STORE_ABSENT")
    proof = environment_proof(pinned, Path(".local/phase5_b1e/probe").resolve())
    binding = persisted_binding(pinned, proof)
    return {"binding": binding, "account_store_present": True, "runtime_authenticated": False}


def runtime_matches(login: int, expected: dict[str, Any]) -> bool:
    actual = hashlib.sha256(UUID(expected["account_binding_id"]).bytes + str(login).encode())
    return bool(actual.hexdigest() == expected["account_fingerprint"])


def qualification_result(
    lifecycle: dict[str, Any], records: list[dict[str, str]], runtime: dict[str, Any], expert: str
) -> dict[str, Any]:
    text = "\n".join(r["message"] for r in records if r["source"].startswith("Tester/"))
    loaded = expert in text and "loaded" in text.lower()
    failed = any(
        marker in text
        for marker in (
            "REFERENCE_REJECTED",
            "REFERENCE_INVALID_EMA_PERIODS",
            "REFERENCE_FIXED_VOLUME_UNSUPPORTED",
            "OnInit failed",
            "initialization failed",
        )
    )
    # A completed native test after loading this exact Expert establishes successful OnInit.
    initialized = False
    for source in {r["source"] for r in records if r["source"].startswith("Tester/")}:
        messages = [r["message"] for r in records if r["source"] == source]
        seen = False
        for message in messages:
            if expert in message and "loaded" in message.lower():
                seen = True
            if seen and "Test passed" in message and not failed:
                initialized = True
    accepted = runtime.get("state") == "RUNTIME_ACCOUNT_CONTEXT_ACCEPTED"
    lifecycle = dict(lifecycle)
    # Existing agents can emit their startup banner before log offsets are captured.
    # An owned tester child plus this exact Expert's ordered native test is stronger
    # evidence than requiring that older banner to be repeated in the appended log.
    if (
        initialized
        and accepted
        and lifecycle.get("config_accepted")
        and "TESTER_SUBSYSTEM_STARTING" in lifecycle.get("stages", [])
    ):
        lifecycle["tester_initialized"] = True
        lifecycle["stages"] = [
            *lifecycle["stages"],
            "TESTER_INITIALIZED",
            "EXPERT_LOADED",
            "EXPERT_ONINIT_SUCCEEDED",
            "BOOTSTRAP_READY",
        ]
    ready = bool(
        accepted
        and lifecycle["tester_initialized"]
        and initialized
        and lifecycle["cleanup_verified"]
    )
    status = "EXECUTION_ENVIRONMENT_READY" if ready else "BOOTSTRAP_UNVERIFIED"
    if "tester not started because the account is not specified" in text:
        status = "ACCOUNT_CONTEXT_FAILURE"
    if failed:
        status = "BLOCKED_REFERENCE_ARTIFACT_DEFECT"
    if runtime.get("state") == "BLOCKED_ACCOUNT_FINGERPRINT_MISMATCH":
        status = runtime["state"]
    return {
        "status": status,
        "environment": "READY" if ready else "UNQUALIFIED",
        "account_context": runtime,
        "lifecycle": lifecycle,
        "expert_loaded": loaded,
        "expert_oninit": "SUCCEEDED" if initialized else "FAILED" if failed else "UNVERIFIED",
        "requested_model": "EVERY_TICK_BASED_ON_REAL_TICKS",
        "native_model_observed": "generating based on real ticks" in text.lower(),
        "full_interval_real_tick_coverage": "UNKNOWN",
        "campaign_authorization": "NOT_AUTHORIZED",
        "start_eligible": False,
        "campaign_budget_consumed": 0,
        "restored_chart_experts": [
            r["message"]
            for r in records
            if r["source"].startswith("logs/")
            and r["component"] == "Experts"
            and "loaded" in r["message"].lower()
        ],
    }


def qualified_evidence(root: Path) -> dict[str, Any]:
    """Read-only derived qualification; retain original assessment and manifest verbatim."""
    manifest = json.loads((root / "manifest.json").read_bytes())
    if digest({"status": manifest["status"], "files": manifest["files"]}) != manifest["identity"]:
        raise ValueError("QUALIFICATION_MANIFEST_CHANGED")
    for name, expected in manifest["files"].items():
        path = local_path(root / name)
        if path.parent != root or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("QUALIFICATION_EVIDENCE_CHANGED")
    original = json.loads((root / "assessment.json").read_bytes())
    dry = json.loads((root / "dry-run.json").read_bytes())
    records = json.loads((root / "observations.json").read_bytes())
    result = qualification_result(
        original["lifecycle"], records, original["account_context"], UUID(original["probe_id"]).hex
    )
    content = {
        "schema": "PHASE5C2D_QUALIFICATION_V1",
        "original_evidence_identity": manifest["identity"],
        "probe_id": original["probe_id"],
        "binding": dry["binding"],
        "assessment": result,
        "exit_code": original["exit_code"],
    }
    return {"content": content, "identity": digest(content)}


def run(root: Path, artifact: Path) -> dict[str, Any]:
    root = local_path(root)
    if not root.is_relative_to(Path(".local/phase5_c2d").resolve()):
        raise ValueError("IGNORED_QUALIFICATION_ROOT_REQUIRED")
    pinned = TerminalBinding.model_validate_json(
        Path(".local/phase5_b/terminal-binding.json").read_bytes()
    )
    dry = offline(pinned, artifact)
    root.mkdir(exist_ok=False)
    restrict_runtime(root)
    identity = uuid4()
    config = Configuration(
        baseline_run_id=identity,
        project_id=UUID("782bd6a2-4f97-5ca4-906a-cbc1dfe5ce2b"),
        symbol="XAUUSDm",
        timeframe="M5",
        from_date=date(2026, 1, 5),
        to_date=date(2026, 1, 6),
        initial_deposit=Decimal("300"),
        leverage=100,
        timeout_seconds=60,
        input_provenance="USER_CONFIRMED_VALUES",
        input_reference="PROJECT_SOURCE qualification only",
        set_text=INPUTS,
    )
    text = configuration_text(config, identity.hex, identity.hex + ".htm", pinned.server)
    validate_config(text, config, pinned.server)
    profile = local_path(pinned.terminal_data_root)
    expert = local_path(profile / "MQL5/Experts" / (identity.hex + ".ex5"))
    params = local_path(profile / "MQL5/Profiles/Tester" / (identity.hex + ".set"))
    ini = root / "qualification.ini"
    if expert.exists() or params.exists() or list(profile.glob(identity.hex + "*")):
        raise ValueError("QUALIFICATION_NAMESPACE_COLLISION")
    roots = {
        "logs": profile / "logs",
        "Tester/terminal": profile / "Tester/logs",
        "Tester/agents": Path(os.environ["APPDATA"]) / "MetaQuotes/Tester" / profile.name,
    }
    before = log_positions(roots)
    protected = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (profile / "MQL5/Experts").rglob("*.ex5")
        if local_path(p).is_file()
    }
    write_json(root / "dry-run.json", dry)
    write_json(
        root / "preregistration.json",
        {
            "kind": "ENVIRONMENT_QUALIFICATION",
            "probe_id": str(identity),
            "max_launches": 1,
            "binding_identity": dry["binding"]["identity"],
            "configuration": config.model_dump(mode="json"),
            "allowed_mutations": [
                str(expert),
                str(params),
                str(ini),
                identity.hex + " report assets",
            ],
            "registered_at": datetime.now(UTC).isoformat(),
        },
    )
    runtime: dict[str, Any] = {"state": "RUNTIME_ACCOUNT_CONTEXT_UNVERIFIED"}
    login: int | None = None
    last_check = time.monotonic()
    cancel = Event()
    observer = Observer(pinned.terminal_executable.parent)
    owned: list[Path] = []

    def observe(pid: int, event: str) -> None:
        nonlocal login, last_check
        observer(pid, event)
        if event != "POLL" or login is not None or time.monotonic() - last_check < 2:
            return
        last_check = time.monotonic()
        try:
            context = discover(pinned)
            if context.process_id != pid or not runtime_matches(
                context.login, dry["binding"]["content"]
            ):
                runtime["state"] = "BLOCKED_ACCOUNT_FINGERPRINT_MISMATCH"
                cancel.set()
                return
            login = context.login
            runtime.update(
                state="RUNTIME_ACCOUNT_CONTEXT_ACCEPTED",
                account_type="DEMO",
                server=context.binding.server,
                company=context.binding.company,
                account_fingerprint=dry["binding"]["content"]["account_fingerprint"],
            )
        except AccountBlocked as error:
            runtime["last_observation"] = str(error)

    lock = Path(".local/phase5_c2d/profile-execution.lock")
    with lock.open("x"):
        pass
    try:
        ownership_ready()
        for path, content in (
            (expert, artifact.read_bytes()),
            (params, INPUTS.encode()),
            (ini, text.encode()),
        ):
            with path.open("xb") as stream:
                stream.write(content)
            owned.append(path)
        if hashlib.sha256(expert.read_bytes()).hexdigest() != ARTIFACT:
            raise ValueError("BLOCKED_ARTIFACT_IDENTITY_MISMATCH")
        write_json(root / "launch.json", {"probe_id": str(identity), "maximum_launches": 1})
        outcome = execute(
            pinned.terminal_executable,
            ["/config:" + str(ini)],
            pinned.terminal_executable.parent,
            60,
            cancel,
            observe,
        )
    finally:
        observer.close()
        for path in owned:
            path.unlink()
        lock.unlink()
        remove_probe_reports(profile, identity)
        capture_logs(
            roots, before, root / "readback", login if login is not None else 999999999999999999
        )
    processes = list(observer.processes.values())
    cleanup = bool(processes) and all(p["end_observed_at"] for p in processes)
    for protected_path, expected in protected.items():
        if hashlib.sha256(Path(protected_path).read_bytes()).hexdigest() != expected:
            raise ValueError("UNRELATED_EXPERT_CHANGED")
    records = journal(root / "readback")
    lifecycle = classify(processes, records, str(ini), "6230", "BOOTSTRAP_UNVERIFIED", cleanup)
    result = qualification_result(lifecycle, records, runtime, identity.hex)
    result.update(
        probe_id=str(identity),
        binding_identity=dry["binding"]["identity"],
        exit_code=outcome.code,
        timed_out=outcome.timed_out,
        protected_experts_unchanged=True,
    )
    write_json(root / "processes.json", processes)
    write_json(root / "observations.json", records)
    write_json(root / "assessment.json", result)
    result["evidence_identity"] = finalize(root, result["status"])
    return result
