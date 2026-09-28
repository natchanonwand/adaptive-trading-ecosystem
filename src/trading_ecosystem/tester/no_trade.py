"""Fixed project-owned no-trade diagnostic. No source upload or candidate execution API."""

import hashlib
import re
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

from trading_ecosystem.tester.bootstrap import probe
from trading_ecosystem.tester.contracts import Configuration
from trading_ecosystem.tester.environment import (
    TerminalBinding,
    file_identity,
    local_path,
    validate_binding,
)
from trading_ecosystem.tester.evidence import write_json
from trading_ecosystem.tester.handshake import Observer, classify, journal, sanitize
from trading_ecosystem.tester.process import Outcome, execute

SOURCE_SHA = (
    "5ed1af298c18aabd9223eb7988eb84c79f610289bdb2db925e4a85a68afa62de"  # pragma: allowlist secret
)
WINDOW_SECONDS = 60.0
COMPILER_SECONDS = 60.0


def fixed_source() -> bytes:
    source = Path(__file__).with_name("probe_expert.mq5").read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError("FIXED_PROBE_SOURCE_CHANGED")
    return source


def compilation_valid(outcome: Outcome, diagnostic: str, ex5: Path) -> bool:
    return (
        not outcome.timed_out
        and not outcome.cancelled
        # The pinned MetaEditor 6230 returned 1 with zero errors and a fresh EX5.
        and outcome.code in {0, 1}
        and re.search(r"(?m)^Result: 0 errors, 0 warnings(?:,.*)?$", diagnostic.strip()) is not None
        and ex5.is_file()
        and ex5.stat().st_size > 0
    )


def compile_probe(
    binding: TerminalBinding,
    root: Path,
    process: Callable[[Path, list[str], Path, float, Event], Outcome] = execute,
) -> dict[str, Any]:
    validate_binding(binding)
    source = fixed_source()
    compiler = local_path(binding.terminal_executable.parent / "metaeditor64.exe")
    result: dict[str, Any] = {
        "status": "BLOCKED_PROBE_COMPILER_UNAVAILABLE",
        "source_sha256": SOURCE_SHA,
    }
    if not compiler.is_file():
        return result
    identity = file_identity(compiler)
    result.update(
        compiler_path=str(compiler),
        compiler_identity=identity,
        compiler_sha256=hashlib.sha256(compiler.read_bytes()).hexdigest(),
        compiler_classification="PINNED_INSTALLATION_LOCAL_PORTABLE_COPY",
    )
    if identity["company"] != binding.company or identity["build"] != binding.terminal_build:
        return result
    root = local_path(root)
    root.mkdir(parents=True, exist_ok=False)
    for src in (compiler, *compiler.parent.glob("*.dll")):
        local_path(src)
        shutil.copyfile(src, root / src.name)
    target = root / "Phase5BNoTradeProbe.mq5"
    target.write_bytes(source)
    exe = root / compiler.name
    if hashlib.sha256(exe.read_bytes()).hexdigest() != result["compiler_sha256"]:
        raise ValueError("COMPILER_COPY_CHANGED")
    outcome = process(
        exe, ["/portable", "/compile:" + str(target), "/log"], root, COMPILER_SECONDS, Event()
    )
    log = target.with_suffix(".log")
    data = log.read_bytes() if log.exists() else b""
    text = data.decode(
        "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig", errors="replace"
    )
    diagnostic = sanitize(text)
    result.update(exit_code=outcome.code, timed_out=outcome.timed_out, diagnostics=diagnostic)
    generated = target.with_suffix(".ex5")
    result["status"] = (
        "COMPILED"
        if compilation_valid(outcome, diagnostic, generated)
        else "PROBE_COMPILATION_FAILED"
    )
    if result["status"] == "COMPILED":
        result.update(
            ex5_path=str(generated), ex5_sha256=hashlib.sha256(generated.read_bytes()).hexdigest()
        )
    write_json(root / "compilation.json", result)
    return result


def marker_assessment(
    processes: list[dict[str, Any]],
    records: list[dict[str, str]],
    config: Configuration,
    ini: str,
    build: str,
    outcome: str,
    cleanup: bool,
    normal_exit: bool,
) -> dict[str, Any]:
    result = classify(processes, records, ini, build, outcome, cleanup)
    result["native_blocker"] = (
        "TESTER_ACCOUNT_NOT_SPECIFIED"
        if any(
            r["component"] == "Tester"
            and r["message"] == "tester not started because the account is not specified"
            for r in records
        )
        else None
    )
    stages = result["stages"][:3]
    init = tick = deinit = False
    component = f"{config.baseline_run_id.hex} ({config.symbol},{config.timeframe})"
    # Markers must come from the exact generated Expert's component in an owned agent log.
    for source in {r["source"] for r in records if r["source"].startswith("Tester/")}:
        seen_init = seen_tick = seen_deinit = False
        for r in (r for r in records if r["source"] == source and r["component"] == component):
            message = re.sub(r"^\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}   ", "", r["message"])
            if message == "PHASE5B_PROBE_INIT_OK":
                seen_init = True
            elif message == "PHASE5B_PROBE_FIRST_TICK" and seen_init:
                seen_tick = True
            elif re.fullmatch(r"PHASE5B_PROBE_DEINIT:\d+", message) and seen_tick:
                seen_deinit = True
        init |= seen_init
        tick |= seen_init and seen_tick
        deinit |= seen_init and seen_tick and seen_deinit
    corroborated = stages[-1] == "CONFIG_ACCEPTED" and any(
        p.get("role") == "tester" and p.get("identity_verified") for p in processes
    )
    init, tick, deinit = init and corroborated, tick and corroborated, deinit and corroborated
    if init:
        stages += ["PROBE_EXPERT_LOADED", "PROBE_INIT_SUCCEEDED", "TESTER_INITIALIZED"]
        result["status"] = "TESTER_INITIALIZED"
    if tick:
        stages.append("FIRST_TICK_OBSERVED")
        if cleanup and normal_exit and deinit:
            stages.append("BOOTSTRAP_READY")
            result["status"] = "BOOTSTRAP_READY"
    result.update(
        stages=stages,
        probe_init_succeeded=init,
        first_tick_observed=tick,
        tester_initialized=init,
        native_stop_observed=deinit and normal_exit,
        current_symbol_status="FIRST_TICK_OBSERVED" if tick else "UNKNOWN",
        real_tick_readiness="UNKNOWN",
        full_interval_real_ticks="UNKNOWN",
    )
    return result


def run_no_trade(binding: TerminalBinding, root: Path, saved: Configuration) -> dict[str, Any]:
    root = local_path(root)
    root.mkdir(parents=True, exist_ok=True)
    identity = uuid4()
    write_json(
        root / "preregistration.json",
        {
            "probe_id": str(identity),
            "maximum_native_launches": 1,
            "window_seconds": WINDOW_SECONDS,
            "compiler_timeout_seconds": COMPILER_SECONDS,
            "registered_at": datetime.now(UTC).isoformat(),
            "source_sha256": SOURCE_SHA,
            "baseline_timeout_seconds": saved.timeout_seconds,
        },
    )
    compiled = compile_probe(binding, root / "compiler")
    if compiled["status"] != "COMPILED":
        write_json(root / "assessment.json", compiled)
        return compiled
    return _execute_compiled(binding, root, saved, compiled, identity)


def _execute_compiled(
    binding: TerminalBinding,
    root: Path,
    saved: Configuration,
    compiled: dict[str, Any],
    identity: UUID,
) -> dict[str, Any]:
    root = local_path(root)
    generated = local_path(Path(compiled["ex5_path"]))
    if (
        generated != root / "compiler/Phase5BNoTradeProbe.ex5"
        or compiled["source_sha256"] != SOURCE_SHA
        or (root / "compiler/Phase5BNoTradeProbe.mq5").read_bytes() != fixed_source()
        or compiled["status"] != "COMPILED"
    ):
        raise ValueError("FIXED_COMPILED_PROBE_REQUIRED")
    validate_binding(binding)
    write_json(root / "native-launch.json", {"probe_id": str(identity), "maximum_launches": 1})
    # Only an in-memory diagnostic identity is derived; no persistence/database interaction.
    config = saved.model_copy(
        update={
            "baseline_run_id": identity,
            "set_text": None,
            "input_provenance": "TESTER_DEFAULTS",
            "input_reference": None,
        }
    )
    observations: list[dict[str, Any]] = []

    def observed(exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event) -> Outcome:
        if timeout != WINDOW_SECONDS:
            raise ValueError("FIXED_WINDOW_REQUIRED")
        binary = Path(compiled["ex5_path"]).read_bytes()
        if hashlib.sha256(binary).hexdigest() != compiled["ex5_sha256"]:
            raise ValueError("COMPILED_PROBE_CHANGED")
        expert = cwd / "MQL5/Experts" / (identity.hex + ".ex5")
        with expert.open("xb") as stream:
            stream.write(binary)
        if hashlib.sha256(expert.read_bytes()).hexdigest() != compiled["ex5_sha256"]:
            raise ValueError("STAGED_PROBE_CHANGED")
        observer = Observer(cwd)
        try:
            # The fixed Expert uses TesterStop; do not cancel it merely on its init marker.
            return execute(exe, args, cwd, timeout, cancel, observer)
        finally:
            observations.extend(observer.processes.values())
            observer.close()
            for folder in (cwd / "logs", cwd / "Tester"):
                for path in folder.rglob("*.log"):
                    local_path(path)
                    raw = path.read_bytes()
                    text = raw.decode(
                        "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig",
                        errors="replace",
                    )
                    safe = sanitize(text)
                    if safe != text.rstrip("\r\n").replace("\r\n", "\n"):
                        path.write_text(safe, encoding="utf-8", newline="\n")

    raw = probe(
        binding, root / "probes", config, observed, window_seconds=WINDOW_SECONDS, probe_id=identity
    )
    records = journal(Path(str(raw.get("working_directory", root))))
    cleanup = bool(observations) and all(p["end_observed_at"] for p in observations)
    ended = (
        "BOOTSTRAP_TIMEOUT"
        if raw.get("timed_out")
        else "PROCESS_EXITED_DURING_BOOTSTRAP"
        if raw.get("process_created")
        else "PROCESS_START_FAILED"
    )
    assessment = marker_assessment(
        observations,
        records,
        config,
        str(raw.get("config_path", "")),
        binding.terminal_build,
        ended,
        cleanup,
        raw.get("exit_code") == 0,
    )
    result = {
        **raw,
        **assessment,
        "probe_expert_id": str(identity),
        "compilation": compiled,
        "observations": records,
        "processes": observations,
        "expert_intentionally_absent": False,
        "candidate_staged": False,
        "internal_probe_staged": bool(observations),
        "schema": "PHASE5B1D_NO_TRADE_V1",
    }
    write_json(root / "native-assessment.json", result)
    write_json(
        root / "files.json",
        {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        },
    )
    return result
