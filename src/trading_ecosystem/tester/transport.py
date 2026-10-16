"""Offline diagnostic transport interpretation; no execution or research mutations."""

import hashlib
from pathlib import Path
from typing import Any

from trading_ecosystem.tester.environment import local_path
from trading_ecosystem.tester.qualification import digest

PROBE = "RuntimeTransportProbe"


def sandbox_path(data_root: Path) -> Path:
    root = local_path(data_root)
    result = local_path(root / "MQL5" / "Files" / (PROBE + ".txt"))
    if not result.is_relative_to(root):
        raise ValueError("BLOCKED_EVIDENCE_READBACK")
    return result


def assess_transport(
    raw: bytes | None,
    data_root: Path,
    *,
    terminal_started: bool,
    dispatched: bool,
    script_returned: bool,
    normal_exit: bool,
    write_failed: bool = False,
    runtime_failed: bool = False,
    tester_observed: bool = False,
) -> dict[str, Any]:
    """Keep payload completion, observed return and normal shutdown independent."""
    started = complete = verified = False
    payload: dict[str, str] | None = None
    malformed = False
    if raw is not None:
        try:
            if len(raw) > 8192:
                raise ValueError("OVERSIZE")
            lines = raw.decode("utf-8-sig", errors="strict").splitlines()
            started = bool(lines and lines[0] == "STARTED")
            complete = bool(lines and lines[-1] == "COMPLETED")
            if started and complete:
                pairs = [line.split("=", 1) for line in lines[1:-1]]
                if any(len(pair) != 2 for pair in pairs):
                    raise ValueError("INVALID_METADATA")
                payload = dict(pairs)
                if len(payload) != len(pairs) or set(payload) != {
                    "schema",
                    "script",
                    "version",
                    "build",
                    "data_path",
                }:
                    raise ValueError("UNEXPECTED_FIELDS")
                verified = (
                    payload["schema"] == "RUNTIME_TRANSPORT_V1"
                    and payload["script"] == PROBE
                    and payload["version"] == "1.00"
                    and payload["build"] == "6230"
                    and local_path(Path(payload["data_path"])) == local_path(data_root)
                )
                malformed = not verified
        except (ValueError, OSError, UnicodeError):
            malformed = True
    if tester_observed:
        status = "BLOCKED_UNEXPECTED_TESTER_PROCESS"
    elif write_failed:
        status = "BLOCKED_EVIDENCE_FILE_WRITE"
    elif malformed or (raw is not None and not started):
        status = "BLOCKED_EVIDENCE_READBACK"
    elif runtime_failed or (started and not complete):
        status = "BLOCKED_SCRIPT_RUNTIME"
    elif not started:
        status = "UNKNOWN_TRANSPORT_FAILURE" if dispatched else "BLOCKED_STARTUP_SCRIPT_DISPATCH"
    elif not script_returned:
        status = "BLOCKED_SCRIPT_RUNTIME"
    elif not normal_exit:
        status = "BLOCKED_SCRIPT_DRIVEN_SHUTDOWN"
    elif terminal_started and dispatched and verified:
        status = "RUNTIME_ATTESTATION_TRANSPORT_READY"
    else:
        status = "UNKNOWN_TRANSPORT_FAILURE"
    return {
        "status": status,
        "terminal_started": terminal_started,
        "startup_script_load_observed": dispatched,
        "onstart_verified": started or write_failed,
        "start_marker": started,
        "complete_marker": complete,
        "readback_verified": verified,
        "script_returned": script_returned,
        "normal_terminal_exit": normal_exit,
        "file_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "payload_identity": digest(payload) if verified else None,
        "payload": payload if verified else None,
        "profile_isolation": "NOT_ASSESSED",
    }
