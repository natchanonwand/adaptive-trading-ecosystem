"""Bounded terminal-only probe: no candidate, account profile, run or result record."""

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from threading import Event
from uuid import uuid4

from trading_ecosystem.tester.environment import (
    EnvironmentError,
    TerminalBinding,
    local_path,
    validate_binding,
)
from trading_ecosystem.tester.process import Outcome, execute


def probe(
    binding: TerminalBinding,
    root: Path,
    process: Callable[[Path, list[str], Path, float, Event], Outcome] = execute,
) -> dict[str, object]:
    result: dict[str, object] = {
        "kind": "ENVIRONMENT_BOOTSTRAP_PROBE",
        "probe_id": str(uuid4()),
        "process_created": False,
        "baseline_result": False,
    }
    try:
        validate_binding(binding)
    except (EnvironmentError, OSError) as error:
        result["status"] = (
            str(error) if isinstance(error, EnvironmentError) else "BLOCKED_TESTER_DATA_ROOT"
        )
        return result
    runtime = local_path(root) / str(result["probe_id"])
    runtime.mkdir(parents=True, exist_ok=False)
    exe = binding.terminal_executable
    for source in (exe, exe.parent / "metatester64.exe", *exe.parent.glob("*.dll")):
        local_path(source)
        shutil.copyfile(source, runtime / source.name)
    ini = runtime / "bootstrap.ini"
    ini.write_text(
        "[Experts]\nEnabled=0\nAllowLiveTrading=0\nAllowDllImport=0\n[StartUp]\nExpert=\nScript=\n",
        encoding="utf-8",
    )
    args = ["/portable", "/config:" + str(ini)]
    result.update(arguments=args, working_directory=str(runtime), config_path=str(ini))
    try:
        outcome = process(runtime / exe.name, args, runtime, 10.0, Event())
        result.update(process_created=True, exit_code=outcome.code, timed_out=outcome.timed_out)
        # Survival is not proof of tester initialization; never report acceptance success.
        result["status"] = (
            "BOOTSTRAP_UNVERIFIED" if outcome.timed_out else "PROCESS_EXITED_DURING_BOOTSTRAP"
        )
    except (OSError, ValueError):
        result["status"] = "PROCESS_START_FAILED"
    (runtime / "probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
