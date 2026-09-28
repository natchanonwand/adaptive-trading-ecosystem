"""Bounded terminal-only probe: no candidate, account profile, run or result record."""

import hashlib
import json
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from uuid import uuid4

from trading_ecosystem.tester.adapter import configuration_text
from trading_ecosystem.tester.contracts import Configuration
from trading_ecosystem.tester.environment import (
    EnvironmentError,
    TerminalBinding,
    local_path,
    validate_binding,
    validate_config,
)
from trading_ecosystem.tester.evidence import logs
from trading_ecosystem.tester.process import Outcome, execute


def assess_probe(result: dict[str, object], diagnostic: str) -> dict[str, object]:
    """Conservative readback: terminal startup is not tester initialization."""
    assessed = dict(result)
    config_path = str(result.get("config_path", ""))
    accepted = f'successfully initialized from start config "{config_path}"'
    assessed["configuration_accepted"] = (
        "OBSERVED" if config_path and accepted in diagnostic else "UNKNOWN"
    )
    build = str(result.get("terminal_build", ""))
    assessed["native_build_observed"] = bool(
        build and f"MetaTrader 5 x64 build {build} started" in diagnostic
    )
    if result.get("timed_out"):
        assessed["status"] = "TIMEOUT"
        assessed["reason"] = "NATIVE_TESTER_INITIALIZATION_NOT_VERIFIED_WITHIN_PROBE_BOUND"
    return assessed


def probe(
    binding: TerminalBinding,
    root: Path,
    config: Configuration,
    process: Callable[[Path, list[str], Path, float, Event], Outcome] = execute,
) -> dict[str, object]:
    result: dict[str, object] = {
        "kind": "ENVIRONMENT_BOOTSTRAP_PROBE",
        "probe_id": str(uuid4()),
        "process_created": False,
        "baseline_result": False,
        "candidate_staged": False,
        "terminal_build": binding.terminal_build,
        "terminal_sha256": binding.terminal_sha256,
        "terminal_binding_id": str(binding.terminal_binding_id),
        "configuration_accepted": "UNKNOWN",
        "tester_initialized": "UNKNOWN",
        "history_status": "UNKNOWN",
        "real_ticks_status": "UNKNOWN",
        "started_at": datetime.now(UTC).isoformat(),
    }
    try:
        validate_binding(binding)
    except (EnvironmentError, OSError) as error:
        result["status"] = (
            str(error) if isinstance(error, EnvironmentError) else "BLOCKED_TESTER_DATA_ROOT"
        )
        return result
    runtime = local_path(root) / str(result["probe_id"])
    try:
        runtime.mkdir(parents=True, exist_ok=False)
        for folder in ("MQL5/Experts", "MQL5/Profiles/Tester", "reports"):
            target = runtime / folder
            target.mkdir(parents=True, exist_ok=False)
            with (target / "write-check").open("xb") as stream:
                stream.write(b"owned runtime write check")
        result["runtime_output_writable"] = True
    except OSError:
        result["status"] = "BLOCKED_TESTER_RUNTIME_DIRECTORY"
        return result
    exe = binding.terminal_executable
    for source in (exe, exe.parent / "metatester64.exe", *exe.parent.glob("*.dll")):
        local_path(source)
        shutil.copyfile(source, runtime / source.name)
    ini = runtime / "bootstrap.ini"
    # Exact research parameters, but an intentionally absent expert in an empty portable root.
    # No candidate, account, profile or cache is copied. A missing expert cannot trade.
    text = configuration_text(
        config, config.baseline_run_id.hex, config.baseline_run_id.hex + ".htm", binding.server
    )
    validate_config(text, config, binding.server)
    ini.write_text(text, encoding="utf-8")
    result.update(
        config_sha256=hashlib.sha256(ini.read_bytes()).hexdigest(),
        config_validation="PASS",
        configured_timeout_seconds=config.timeout_seconds,
        probe_timeout_seconds=10,
        expert_intentionally_absent=True,
    )
    args = ["/portable", "/config:" + str(ini)]
    result.update(arguments=args, working_directory=str(runtime), config_path=str(ini))
    try:
        if hashlib.sha256((runtime / exe.name).read_bytes()).hexdigest() != binding.terminal_sha256:
            raise ValueError("PINNED_EXECUTABLE_CHANGED")
        outcome = process(runtime / exe.name, args, runtime, 10.0, Event())
        result.update(process_created=True, exit_code=outcome.code, timed_out=outcome.timed_out)
        # Survival is not proof of tester initialization; never report acceptance success.
        result["status"] = (
            "BOOTSTRAP_UNVERIFIED" if outcome.timed_out else "PROCESS_EXITED_DURING_BOOTSTRAP"
        )
    except (OSError, ValueError) as error:
        result["status"] = "PROCESS_START_FAILED"
        result["native_error_code"] = getattr(error, "winerror", None)
    diagnostic = logs(runtime)
    (runtime / "diagnostic.txt").write_text(diagnostic, encoding="utf-8", newline="\n")
    result["diagnostic_sha256"] = hashlib.sha256(
        (runtime / "diagnostic.txt").read_bytes()
    ).hexdigest()
    result["finished_at"] = datetime.now(UTC).isoformat()
    result = assess_probe(result, diagnostic)
    (runtime / "probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
