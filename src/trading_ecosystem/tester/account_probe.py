"""One fixed no-trade probe in the verified existing profile; no credential copying."""

import hashlib
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

from trading_ecosystem.tester.adapter import configuration_text
from trading_ecosystem.tester.contracts import Configuration
from trading_ecosystem.tester.environment import TerminalBinding, local_path, validate_config
from trading_ecosystem.tester.evidence import write_json
from trading_ecosystem.tester.handshake import Observer, journal, sanitize
from trading_ecosystem.tester.no_trade import (
    SOURCE_SHA,
    WINDOW_SECONDS,
    compile_probe,
    marker_assessment,
)
from trading_ecosystem.tester.process import execute
from trading_ecosystem.tester.research_account import (
    AccountBlocked,
    AccountContext,
    account_config,
    discover,
    running_terminals,
)


@contextmanager
def ephemeral_ini(path: Path, base: str, context: AccountContext) -> Iterator[None]:
    created = False
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(account_config(base, context))
        yield
    finally:
        # No raw-account config or its hash is retained as diagnostic evidence.
        if created and path.exists():
            path.unlink()


def log_positions(roots: dict[str, Path]) -> dict[str, int]:
    return {
        str(local_path(p)): p.stat().st_size
        for root in roots.values()
        for p in root.rglob("*.log")
        if p.is_file()
    }


def capture_logs(roots: dict[str, Path], before: dict[str, int], target: Path, login: int) -> None:
    total = 0
    for label, root in roots.items():
        for path in root.rglob("*.log"):
            local_path(path)
            offset = before.get(str(path.resolve()), 0)
            if path.stat().st_size < offset:
                raise ValueError("NATIVE_LOG_TRUNCATED")
            with path.open("rb") as stream:
                bom = stream.read(2)
                stream.seek(offset)
                raw = stream.read(8 * 1024**2 + 1)
            total += len(raw)
            if total > 8 * 1024**2:
                raise ValueError("PROBE_LOG_SIZE_LIMIT")
            if not raw:
                continue
            encoding = "utf-16-le" if bom == b"\xff\xfe" else "utf-8-sig"
            text = raw.decode(encoding, errors="replace").lstrip("\ufeff")
            safe = sanitize(text.replace(str(login), "[ACCOUNT_REDACTED]"))
            output = target / label / path.relative_to(root)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(safe)


def close_session(context: AccountContext, pinned: TerminalBinding) -> None:
    rows = running_terminals()
    if len(rows) != 1 or rows[0]["ProcessId"] != context.process_id:
        raise AccountBlocked("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
    if Path(rows[0]["ExecutablePath"]).resolve() != pinned.terminal_executable.resolve():
        raise AccountBlocked("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
    # Graceful close only; do not kill an unrelated or non-responsive operator process.
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"$p=Get-Process -Id {context.process_id} -ErrorAction Stop; "
            "if (-not $p.CloseMainWindow()) { exit 1 }; "
            "if (-not $p.WaitForExit(10000)) { exit 2 }",
        ],
        capture_output=True,
        timeout=15,
        check=False,
    )
    if result.returncode or running_terminals():
        raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_CONTEXT_UNAVAILABLE")


def restrict_runtime(root: Path) -> None:
    sid = subprocess.check_output(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value",
        ],
        text=True,
        timeout=15,
    ).strip()
    subprocess.run(
        ["icacls.exe", str(root), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"],
        check=True,
        capture_output=True,
        timeout=15,
    )


def remove_probe_reports(profile: Path, identity: UUID) -> int:
    """Remove this UUID's native HTML/graphs, which may name the account."""
    removed = 0
    for path in profile.glob(identity.hex + "*"):
        if path.is_file() and path.suffix.lower() in {".htm", ".html", ".png"}:
            local_path(path)
            path.unlink()
            removed += 1
    return removed


def run_account_probe(pinned: TerminalBinding, root: Path, saved: Configuration) -> dict[str, Any]:
    root = local_path(root)
    if saved.symbol != "XAUUSDm" or saved.timeframe != "M5":
        raise ValueError("FIXED_PROBE_MARKET_REQUIRED")
    if not root.is_relative_to(Path(".local/phase5_b1e").resolve()):
        raise ValueError("IGNORED_PROBE_ROOT_REQUIRED")
    root.mkdir(parents=True, exist_ok=False)
    restrict_runtime(root)
    identity = uuid4()
    write_json(
        root / "preregistration.json",
        {
            "probe_id": str(identity),
            "maximum_native_launches": 1,
            "window_seconds": WINDOW_SECONDS,
            "source_sha256": SOURCE_SHA,
            "registered_at": datetime.now(UTC).isoformat(),
            "runtime_profile": "EXISTING_PINNED_PROFILE_NO_CREDENTIAL_COPY",
        },
    )
    context = discover(pinned)
    write_json(root / "account-binding.json", context.binding.model_dump(mode="json"))
    compiled = compile_probe(pinned, root / "compiler")
    if compiled["status"] != "COMPILED":
        write_json(root / "assessment.json", compiled)
        return compiled
    # Re-observe after compilation, before closing the session and materializing its identifier.
    current = discover(pinned)
    if current.login != context.login or current.process_id != context.process_id:
        raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_CONTEXT_UNAVAILABLE")
    config = saved.model_copy(
        update={
            "baseline_run_id": identity,
            "set_text": None,
            "input_provenance": "TESTER_DEFAULTS",
            "input_reference": None,
        }
    )
    base = configuration_text(config, identity.hex, identity.hex + ".htm", pinned.server)
    validate_config(base, config, pinned.server)
    roots = {
        "logs": pinned.terminal_data_root / "logs",
        "Tester/terminal": pinned.terminal_data_root / "Tester/logs",
        "Tester/agents": Path(os.environ["APPDATA"])
        / "MetaQuotes/Tester"
        / pinned.terminal_data_root.name,
    }
    before = log_positions(roots)
    expert = local_path(pinned.terminal_data_root / "MQL5/Experts" / (identity.hex + ".ex5"))
    binary = Path(compiled["ex5_path"]).read_bytes()
    if hashlib.sha256(binary).hexdigest() != compiled["ex5_sha256"]:
        raise ValueError("COMPILED_PROBE_CHANGED")
    ini = root / "account-probe.ini"
    if list(pinned.terminal_data_root.glob(identity.hex + "*")):
        raise ValueError("EXISTING_PROBE_REPORT_NAMESPACE")
    close_session(context, pinned)
    observer = Observer(pinned.terminal_executable.parent)
    staged = False
    try:
        with expert.open("xb") as stream:
            stream.write(binary)
        staged = True
        with ephemeral_ini(ini, base, context):
            write_json(
                root / "native-launch.json", {"probe_id": str(identity), "maximum_launches": 1}
            )
            outcome = execute(
                pinned.terminal_executable,
                ["/config:" + str(ini)],
                pinned.terminal_executable.parent,
                WINDOW_SECONDS,
                Event(),
                observer,
            )
    finally:
        observer.close()
        if staged:
            expert.unlink()
        remove_probe_reports(pinned.terminal_data_root, identity)
        capture_logs(roots, before, root / "readback", context.login)
    processes = list(observer.processes.values())
    cleanup = bool(processes) and all(p["end_observed_at"] for p in processes)
    records = journal(root / "readback")
    assessment = marker_assessment(
        processes,
        records,
        config,
        str(ini),
        pinned.terminal_build,
        "BOOTSTRAP_TIMEOUT" if outcome.timed_out else "PROCESS_EXITED_DURING_BOOTSTRAP",
        cleanup,
        outcome.code == 0,
    )
    result = {
        **assessment,
        "schema": "PHASE5B1E_ACCOUNT_PROBE_V1",
        "probe_id": str(identity),
        "terminal_binding_id": str(pinned.terminal_binding_id),
        "terminal_sha256": pinned.terminal_sha256,
        "terminal_build": pinned.terminal_build,
        "account_binding": context.binding.model_dump(mode="json"),
        "window_seconds": WINDOW_SECONDS,
        "exit_code": outcome.code,
        "timed_out": outcome.timed_out,
        "processes": processes,
        "observations": records,
        "candidate_staged": False,
        "baseline_result": False,
        "ephemeral_config_removed": not ini.exists(),
        "probe_expert_removed": not expert.exists(),
        "compilation": compiled,
        "finished_at": datetime.now(UTC).isoformat(),
    }
    write_json(root / "assessment.json", result)
    write_json(
        root / "files.json",
        {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        },
    )
    return result
