"""Read-only DEMO context discovery. Native identifiers exist only in session memory."""

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from trading_ecosystem.domain.primitives import FrozenModel, UtcTimestamp
from trading_ecosystem.tester.environment import TerminalBinding, validate_binding


class AccountBlocked(ValueError):
    """Only typed, non-sensitive diagnostics escape the SDK boundary."""


class ResearchAccountBinding(FrozenModel):
    account_binding_id: UUID
    terminal_binding_id: UUID
    company: str
    server: str
    environment_classification: Literal["DEMO"] = "DEMO"
    account_fingerprint: str
    verified_at: UtcTimestamp
    discovery_source: Literal["PINNED_RUNNING_SESSION"] = "PINNED_RUNNING_SESSION"


@dataclass(frozen=True)
class AccountContext:
    binding: ResearchAccountBinding
    login: int = field(repr=False)
    process_id: int


def running_terminals() -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "@(Get-CimInstance Win32_Process -Filter \"Name = 'terminal64.exe'\" "
            "-ErrorAction Stop | Select-Object ProcessId,ExecutablePath) "
            "| ConvertTo-Json -Compress",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    rows = json.loads(result.stdout or "[]")
    return [rows] if isinstance(rows, dict) else list(rows)


def assess(
    pinned: TerminalBinding, terminal: dict[str, Any], account: dict[str, Any] | None, pid: int
) -> AccountContext:
    if (
        Path(terminal.get("path", "")).resolve() != pinned.terminal_executable.parent.resolve()
        or Path(terminal.get("data_path", "")).resolve() != pinned.terminal_data_root.resolve()
        or str(terminal.get("build")) != pinned.terminal_build
    ):
        raise AccountBlocked("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
    if not terminal.get("connected") or account is None:
        raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_CONTEXT_UNAVAILABLE")
    if type(account.get("trade_mode")) is not int or account["trade_mode"] != 0:
        raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_NOT_DEMO")
    if (
        account.get("server") != pinned.server
        or account.get("company") != "Exness Technologies Ltd"
    ):
        raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_SERVER_MISMATCH")
    if terminal.get("trade_allowed") is not False:
        raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_CONTEXT_UNAVAILABLE")
    login = account.get("login")
    if type(login) is not int or login <= 0:
        raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_UNBOUND")
    identity = uuid4()
    # Random binding salt prevents a persisted unsalted account-number dictionary lookup.
    fingerprint = hashlib.sha256(identity.bytes + str(login).encode()).hexdigest()
    return AccountContext(
        ResearchAccountBinding(
            account_binding_id=identity,
            terminal_binding_id=pinned.terminal_binding_id,
            company=account["company"],
            server=account["server"],
            account_fingerprint=fingerprint,
            verified_at=datetime.now(UTC),
        ),
        login,
        pid,
    )


def discover(pinned: TerminalBinding) -> AccountContext:
    validate_binding(pinned)
    rows = running_terminals()
    if not rows:
        raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_CONTEXT_UNAVAILABLE")
    if len(rows) != 1 or Path(rows[0].get("ExecutablePath") or "").resolve() != (
        pinned.terminal_executable.resolve()
    ):
        raise AccountBlocked("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
    from trading_ecosystem.discovery.sdk import NativeSdk

    sdk = NativeSdk()._mt5
    try:
        if not sdk.initialize(str(pinned.terminal_executable), timeout=15000):
            raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_CONTEXT_UNAVAILABLE")
        terminal, account = sdk.terminal_info(), sdk.account_info()
        safe_terminal = {
            k: getattr(terminal, k, None)
            for k in ("path", "data_path", "build", "connected", "trade_allowed")
        }
        safe_account = (
            None
            if account is None
            else {
                k: getattr(account, k, None) for k in ("company", "server", "trade_mode", "login")
            }
        )
        return assess(pinned, safe_terminal, safe_account, int(rows[0]["ProcessId"]))
    except AccountBlocked:
        raise
    except Exception:
        raise AccountBlocked("BLOCKED_TESTER_ACCOUNT_CONTEXT_UNAVAILABLE") from None
    finally:
        sdk.shutdown()


def account_config(base: str, context: AccountContext) -> str:
    """Documented Common.Login uses the terminal's own authentication database, never a copy."""
    if base.count("[Common]\n") != 1 or "Login=" in base or "Password=" in base:
        raise ValueError("INVALID_ACCOUNT_CONFIG_BASE")
    return base.replace("[Common]\n", f"[Common]\nLogin={context.login}\n", 1)
