"""Research-only terminal binding and fail-closed cache diagnostics; no broker SDK."""

import configparser
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field

from trading_ecosystem.domain.primitives import FrozenModel, UtcTimestamp
from trading_ecosystem.tester.adapter import Environment, configuration_text
from trading_ecosystem.tester.contracts import Configuration


class EnvironmentError(ValueError):
    """A sanitized, typed local-environment failure."""


class TerminalBinding(FrozenModel):
    terminal_binding_id: UUID
    terminal_executable: Path
    terminal_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    terminal_data_root: Path
    company: str
    product: str
    terminal_build: str
    discovery_source: Literal["INSTALLED_TERMINAL_ORIGIN_MAPPING"]
    verified_at: UtcTimestamp
    environment: Literal["RESEARCH_STRATEGY_TESTER_ONLY"] = "RESEARCH_STRATEGY_TESTER_ONLY"
    broker_name: str
    server: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$")


def local_path(path: Path) -> Path:
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")):
        raise EnvironmentError("BLOCKED_UNSAFE_TERMINAL_PATH")
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise EnvironmentError("BLOCKED_UNSAFE_TERMINAL_PATH")
    return path.resolve()


def select_terminal(candidates: list[Path], profile_root: Path) -> tuple[Path, Path]:
    candidates = sorted({local_path(p) for p in candidates if p.is_file()})
    if not candidates:
        raise EnvironmentError("BLOCKED_TERMINAL_NOT_FOUND")
    if len(candidates) != 1:
        raise EnvironmentError("BLOCKED_TERMINAL_AMBIGUOUS")
    exe = candidates[0]
    matches = []
    if profile_root.is_dir():
        for origin in profile_root.glob("*/origin.txt"):
            raw = origin.read_bytes()
            encoding = (
                "utf-16"
                if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw
                else "utf-8-sig"
            )
            target = raw.decode(encoding).strip()
            if Path(target).resolve() == exe.parent:
                matches.append(local_path(origin.parent))
    if len(matches) != 1:
        raise EnvironmentError("BLOCKED_TESTER_DATA_ROOT")
    return exe, matches[0]


def file_identity(exe: Path) -> dict[str, str]:
    # Fixed PowerShell program; the path is data in the environment, never executable text.
    command = (
        "$v=(Get-Item -LiteralPath $env:PHASE5B_METADATA_FILE).VersionInfo; "
        "@{company=$v.CompanyName;product=$v.ProductName;build=$v.FilePrivatePart} "
        "| ConvertTo-Json -Compress"
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "USERPROFILE"}
    }
    env["PHASE5B_METADATA_FILE"] = str(local_path(exe))
    powershell = (
        Path(os.environ.get("SystemRoot", "C:/Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    result = subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        timeout=15,
        check=False,
        env=env,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise EnvironmentError("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
    value = json.loads(result.stdout)
    return {key: str(value[key]) for key in ("company", "product", "build")}


def discover() -> TerminalBinding:
    candidates: list[Path] = []
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        root = Path(os.environ.get(key, "C:/Program Files"))
        if root.is_dir():
            candidates.extend(root.glob("*/terminal64.exe"))
    exe, data = select_terminal(candidates, Path(os.environ["APPDATA"]) / "MetaQuotes/Terminal")
    identity = file_identity(exe)
    # Reuse the prior successful read-only discovery's sanitized account evidence.
    prior = json.loads(
        Path(".local/phase4_a/demo-smoke-accepted.json").read_text(encoding="utf-8-sig")
    )
    account = prior["latest"]["ACCOUNT:current"]
    if prior["scope"]["environment"] != "DEMO" or account["trade_mode"] != 0:
        raise EnvironmentError("BLOCKED_RESEARCH_ENVIRONMENT")
    return TerminalBinding(
        terminal_binding_id=uuid4(),
        terminal_executable=exe,
        terminal_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        terminal_data_root=data,
        company=identity["company"],
        product=identity["product"],
        terminal_build=identity["build"],
        discovery_source="INSTALLED_TERMINAL_ORIGIN_MAPPING",
        verified_at=datetime.now(UTC),
        broker_name="Exness",
        server=account["server"],
    )


def validate_binding(binding: TerminalBinding, symbol: str = "XAUUSDm") -> Environment:
    exe = local_path(binding.terminal_executable)
    data = local_path(binding.terminal_data_root)
    if not exe.is_file():
        raise EnvironmentError("BLOCKED_TERMINAL_NOT_FOUND")
    if (
        exe.name.lower() != "terminal64.exe"
        or hashlib.sha256(exe.read_bytes()).hexdigest() != binding.terminal_sha256
    ):
        raise EnvironmentError("BLOCKED_TERMINAL_IDENTITY_MISMATCH")
    if not data.is_dir():
        raise EnvironmentError("BLOCKED_TESTER_DATA_ROOT")
    if symbol not in {"XAUUSDm", "BTCUSDm", "USTECm"}:
        raise EnvironmentError("BLOCKED_TESTER_CONFIG_INVALID")
    cache = local_path(data / "bases" / binding.server)
    required = [cache / "symbols.raw", exe.parent / "metatester64.exe"]
    for item in required:
        if not item.is_file():
            raise EnvironmentError("BLOCKED_TESTER_CACHE")
        local_path(item)
        with item.open("rb") as stream:
            stream.read(1)
    for folder, suffix in (("history", "*.hcc"), ("ticks", "*.tkc")):
        files = list((cache / folder / symbol).glob(suffix))
        if not files:
            raise EnvironmentError("BLOCKED_TESTER_CACHE")
        for item in files:
            local_path(item)
            with item.open("rb") as stream:
                stream.read(1)
    return Environment(
        terminal_executable=exe,
        terminal_sha256=binding.terminal_sha256,
        cache_directory=data / "bases",
        broker_name=binding.broker_name,
        server=binding.server,
        terminal_build=binding.terminal_build,
    )


def validate_config(text: str, cfg: Configuration, server: str) -> None:
    parsed = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        parsed.read_string(text)
        required = {
            "expert": cfg.baseline_run_id.hex + ".ex5",
            "symbol": cfg.symbol,
            "period": cfg.timeframe,
            "model": "4",
            "fromdate": cfg.from_date.strftime("%Y.%m.%d"),
            "todate": cfg.to_date.strftime("%Y.%m.%d"),
            "deposit": str(cfg.initial_deposit),
            "currency": cfg.currency,
            "leverage": "1:" + str(cfg.leverage),
            "report": cfg.baseline_run_id.hex + ".htm",
            "optimization": "0",
            "shutdownterminal": "1",
            "usecloud": "0",
            "useremote": "0",
        }
        if not parsed.has_section("Tester") or any(
            parsed["Tester"].get(key) != value for key, value in required.items()
        ):
            raise ValueError
        expected = configparser.ConfigParser(interpolation=None, strict=True)
        expected.read_string(
            configuration_text(
                cfg, cfg.baseline_run_id.hex, cfg.baseline_run_id.hex + ".htm", server
            )
        )
        if {s: dict(parsed[s]) for s in parsed.sections()} != {
            s: dict(expected[s]) for s in expected.sections()
        }:
            raise ValueError
    except (ValueError, configparser.Error):
        raise EnvironmentError("BLOCKED_TESTER_CONFIG_INVALID") from None


def binding_status(path: Path, symbol: str = "XAUUSDm") -> dict[str, Any]:
    if not path.is_file():
        return {"status": "BLOCKED_TERMINAL_NOT_FOUND", "reason": "RESEARCH_BINDING_NOT_CONFIGURED"}
    try:
        binding = TerminalBinding.model_validate_json(path.read_bytes())
        validate_binding(binding, symbol)
        status = "READY"
    except EnvironmentError as error:
        status = str(error)
    except (ValueError, OSError):
        return {"status": "BLOCKED_TESTER_DATA_ROOT", "reason": "BINDING_INVALID_OR_INACCESSIBLE"}
    return {
        "status": status,
        "binding": binding.model_dump(mode="json"),
        "scope": "RESEARCH_ONLY_NOT_BROKER_EXECUTION_AUTHORIZATION",
    }
