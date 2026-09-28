"""Probe-only native handshake observations. Never a candidate execution authorization."""

import ctypes
import hashlib
import re
import time
from ctypes import wintypes as w
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any

from trading_ecosystem.tester.bootstrap import probe
from trading_ecosystem.tester.contracts import Configuration
from trading_ecosystem.tester.environment import TerminalBinding, local_path
from trading_ecosystem.tester.evidence import write_json
from trading_ecosystem.tester.process import Outcome, execute

WINDOW_SECONDS = 45.0


class Entry(ctypes.Structure):
    _fields_ = [
        ("size", w.DWORD),
        ("usage", w.DWORD),
        ("pid", w.DWORD),
        ("heap", ctypes.c_size_t),
        ("module", w.DWORD),
        ("threads", w.DWORD),
        ("parent", w.DWORD),
        ("priority", w.LONG),
        ("flags", w.DWORD),
        ("exe", w.WCHAR * 260),
    ]


def process_snapshot() -> list[tuple[int, int, str]]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    kernel.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError("PROCESS_SNAPSHOT_FAILED")
    result = []
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            result.append((entry.pid, entry.parent, entry.exe))
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return result


def sanitize(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if re.search(r"password|passwd|token|secret|api.?key|license.?key", line, re.I):
            lines.append("[REDACTED SENSITIVE LINE]")
        else:
            line = re.sub(
                r"(?i)((?:login|account)(?:\s+id)?\s*[:=#]?\s*)\d+", r"\1[REDACTED]", line
            )
            line = re.sub(r"(['\"])\d{5,}\1", "'[REDACTED]'", line)
            lines.append(line)
    return "\n".join(lines)


def journal(runtime: Path) -> list[dict[str, str]]:
    """Only newly owned probe logs; exact source, native time and capture time retained."""
    records = []
    total = 0
    for folder in (runtime / "logs", runtime / "Tester"):
        for path in sorted(folder.rglob("*.log")):
            if path.is_symlink() or not path.resolve().is_relative_to(runtime.resolve()):
                raise ValueError("UNSAFE_PROBE_LOG")
            total += path.stat().st_size
            if total > 8 * 1024**2:
                raise ValueError("PROBE_LOG_SIZE_LIMIT")
            raw = path.read_bytes()
            text = raw.decode(
                "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig",
                errors="replace",
            )
            for line in sanitize(text).splitlines():
                fields = line.split("\t", 4)
                if len(fields) == 5 and re.fullmatch(r"\d{2}:\d{2}:\d{2}\.\d{3}", fields[2]):
                    records.append(
                        {
                            "source": path.relative_to(runtime).as_posix(),
                            "native_time": fields[2],
                            "component": fields[3],
                            "message": fields[4],
                            "captured_at": datetime.now(UTC).isoformat(),
                        }
                    )
    return records


def classify(
    processes: list[dict[str, Any]],
    records: list[dict[str, str]],
    config_path: str,
    build: str,
    ended: str,
    cleanup: bool,
) -> dict[str, Any]:
    stages = ["PROCESS_NOT_STARTED"]
    root = any(p.get("role") == "terminal" and p.get("identity_verified") for p in processes)
    child = any(p.get("role") == "tester" and p.get("identity_verified") for p in processes)
    accepted = any(
        r["component"] == "Startup"
        and r["source"].startswith("logs/")
        and r["message"] == f'successfully initialized from start config "{config_path}"'
        for r in records
    )
    # Positive agent journal contract from MetaTrader's official Journal of Testing docs.
    # All three events must occur in order in the SAME fresh agent log, with an owned child.
    initialized = False
    for source in {r["source"] for r in records if r["source"].startswith("Tester/")}:
        phase = 0
        for r in (r for r in records if r["source"] == source):
            if (
                phase == 0
                and r["component"] == "Startup"
                and re.fullmatch(
                    rf"MetaTester 5 x64 build {re.escape(build)}(?: \([^\r\n]*\))?", r["message"]
                )
            ):
                phase = 1
            elif (
                phase == 1
                and r["component"] == "Server"
                and re.fullmatch(r"MetaTester 5 started on 127\.0\.0\.1:\d+", r["message"])
            ):
                phase = 2
            elif (
                phase == 2
                and r["component"] == "Startup"
                and r["message"] == "initialization finished"
            ):
                phase = 3
        initialized |= phase == 3
    if root:
        stages.append("PROCESS_STARTED")
        if accepted:
            stages.append("CONFIG_ACCEPTED")
            if child:
                stages.append("TESTER_SUBSYSTEM_STARTING")
                if initialized:
                    stages.append("TESTER_INITIALIZED")
    status = ended
    rejected = any(
        r["component"] == "Startup"
        and r["source"].startswith("logs/")
        and r["message"] == f'failed to initialize from start config "{config_path}"'
        for r in records
    )
    if root and rejected:
        status = "CONFIG_REJECTED"
    if stages[-1] == "TESTER_INITIALIZED" and cleanup and not rejected:
        stages.append("BOOTSTRAP_READY")
        status = "BOOTSTRAP_READY"
    return {
        "status": status,
        "stages": stages,
        "config_accepted": root and accepted,
        "tester_initialized": stages[-1] in {"TESTER_INITIALIZED", "BOOTSTRAP_READY"},
        "current_symbol_status": "UNKNOWN",
        "real_tick_readiness": "UNKNOWN",
        "cleanup_verified": cleanup,
    }


class Observer:
    """Observe owned ancestry; hold native handles to obtain exit codes after cleanup."""

    def __init__(self, runtime: Path) -> None:
        self.runtime = runtime
        self.processes: dict[int, dict[str, Any]] = {}
        self.handles: dict[int, Any] = {}
        self.last = 0.0
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.kernel.OpenProcess.restype = w.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            w.HANDLE,
            w.DWORD,
            w.LPWSTR,
            ctypes.POINTER(w.DWORD),
        ]
        self.kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        self.kernel.GetProcessTimes.argtypes = [w.HANDLE, *([ctypes.POINTER(w.FILETIME)] * 4)]
        self.kernel.CloseHandle.argtypes = [w.HANDLE]

    def __call__(self, root: int, event: str) -> None:
        if event == "POLL" and time.monotonic() - self.last < 0.25:
            return
        self.last = time.monotonic()
        snapshot = process_snapshot()
        owned = {root, *self.processes}
        for _ in range(len(snapshot)):
            expanded = owned | {pid for pid, parent, _ in snapshot if parent in owned}
            if expanded == owned:
                break
            owned = expanded
        now = datetime.now(UTC).isoformat()
        for pid, parent, name in snapshot:
            if pid not in owned or pid in self.processes:
                continue
            handle = self.kernel.OpenProcess(0x1000, False, pid)
            path = ctypes.create_unicode_buffer(32768)
            length = w.DWORD(len(path))
            resolved = bool(
                handle
                and self.kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length))
            )
            expected = self.runtime / ("terminal64.exe" if pid == root else "metatester64.exe")
            verified = resolved and Path(path.value) == expected and expected.is_file()
            self.processes[pid] = {
                "pid": pid,
                "parent_pid": parent,
                "role": "terminal"
                if pid == root
                else "tester"
                if name.lower() == "metatester64.exe"
                else "other",
                "image": path.value if resolved else "UNKNOWN",
                "identity_verified": verified,
                "sha256": hashlib.sha256(expected.read_bytes()).hexdigest() if verified else None,
                "first_observed_at": now,
                "end_observed_at": None,
                "exit_code": None,
            }
            if handle:
                self.handles[pid] = handle
                self.processes[pid]["start_time"] = self.native_times(handle)[0]
        for pid, handle in list(self.handles.items()):
            code = w.DWORD()
            if self.kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != 259:
                self.processes[pid].update(end_observed_at=now, exit_code=code.value)
                self.processes[pid]["end_time"] = self.native_times(handle)[1]
                self.kernel.CloseHandle(handle)
                del self.handles[pid]

    def native_times(self, handle: Any) -> tuple[str | None, str | None]:
        values = [w.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)):
            return None, None
        result = []
        for value in values[:2]:
            ticks = (value.dwHighDateTime << 32) | value.dwLowDateTime
            result.append(
                datetime.fromtimestamp(ticks / 10_000_000 - 11644473600, UTC).isoformat()
                if ticks
                else None
            )
        return result[0], result[1]

    def close(self) -> None:
        for handle in self.handles.values():
            self.kernel.CloseHandle(handle)
        self.handles.clear()


def run_handshake(binding: TerminalBinding, root: Path, config: Configuration) -> dict[str, Any]:
    """Exclusive preregistration makes interrupted/repeated invocations fail before launch."""
    root = local_path(root)
    root.mkdir(parents=True, exist_ok=True)
    write_json(
        root / "preregistration.json",
        {
            "window_seconds": WINDOW_SECONDS,
            "maximum_launches": 1,
            "registered_at": datetime.now(UTC).isoformat(),
            "baseline_timeout_seconds": config.timeout_seconds,
            "terminal_binding_id": str(binding.terminal_binding_id),
            "candidate_execution": False,
        },
    )
    observations: list[dict[str, Any]] = []
    unexpected_progress = False

    def observed(exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event) -> Outcome:
        nonlocal unexpected_progress
        if timeout != WINDOW_SECONDS:
            raise ValueError("FIXED_WINDOW_REQUIRED")
        if (cwd / "MQL5/Experts" / (config.baseline_run_id.hex + ".ex5")).exists():
            raise ValueError("CANDIDATE_EXECUTION_PROHIBITED")
        observer = Observer(cwd)

        def watch(pid: int, event: str) -> None:
            nonlocal unexpected_progress
            observer(pid, event)
            evidence = journal(cwd)
            current = classify(
                list(observer.processes.values()),
                evidence,
                str(cwd / "bootstrap.ini"),
                binding.terminal_build,
                "BOOTSTRAP_INDETERMINATE",
                False,
            )
            unexpected_progress = unexpected_progress or any(
                r["component"] == "Tester"
                and re.fullmatch(r"testing of .+ started with inputs:", r["message"])
                for r in evidence
            )
            if current["tester_initialized"] or unexpected_progress:
                cancel.set()

        try:
            return execute(exe, args, cwd, timeout, cancel, watch)
        finally:
            observations.extend(observer.processes.values())
            observer.close()
            # Sanitize only this newly generated probe's native logs, never prior evidence.
            for folder in (cwd / "logs", cwd / "Tester"):
                for path in folder.rglob("*.log"):
                    raw = path.read_bytes()
                    text = raw.decode(
                        "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig",
                        errors="replace",
                    )
                    safe = sanitize(text)
                    if safe != text.rstrip("\r\n").replace("\r\n", "\n"):
                        path.write_text(safe, encoding="utf-8", newline="\n")

    raw = probe(binding, root / "probes", config, observed, window_seconds=WINDOW_SECONDS)
    runtime = Path(str(raw.get("working_directory", root)))
    records = journal(runtime)
    cleanup = bool(observations) and all(p["end_observed_at"] for p in observations)
    ended = (
        "BOOTSTRAP_TIMEOUT"
        if raw.get("timed_out")
        else (
            "PROCESS_EXITED_DURING_BOOTSTRAP"
            if raw.get("process_created")
            else "PROCESS_START_FAILED"
        )
    )
    assessment = classify(
        observations,
        records,
        str(raw.get("config_path", "")),
        binding.terminal_build,
        ended,
        cleanup,
    )
    if unexpected_progress or not cleanup and observations:
        assessment["status"] = "BOOTSTRAP_INDETERMINATE"
    result = {
        **raw,
        **assessment,
        "processes": observations,
        "observations": records,
        "window_seconds": WINDOW_SECONDS,
        "schema": "PHASE5B1C_HANDSHAKE_V1",
        "unexpected_progress": unexpected_progress,
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
