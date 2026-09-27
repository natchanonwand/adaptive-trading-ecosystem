"""Offline portable tester staging; never modify the source terminal or authenticate."""

import hashlib
import json
import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event

from pydantic import Field

from trading_ecosystem.domain.primitives import FrozenModel
from trading_ecosystem.tester.contracts import Configuration, State
from trading_ecosystem.tester.process import Outcome, execute


class Blocked(Exception):
    def __init__(self, status: State) -> None:
        self.status = status
        super().__init__(status.value)


class Environment(FrozenModel):
    terminal_executable: Path
    terminal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cache_directory: Path
    broker_name: str = Field(min_length=1, max_length=150)
    server: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$")
    terminal_build: str = Field(pattern=r"^[0-9]{3,8}$")


def load_environment(path: Path, symbol: str = "XAUUSDm") -> Environment:
    binding_path = path.with_name("terminal-binding.json")
    if binding_path.is_file():
        from trading_ecosystem.tester.environment import (
            EnvironmentError,
            TerminalBinding,
            validate_binding,
        )

        try:
            return validate_binding(
                TerminalBinding.model_validate_json(binding_path.read_bytes()), symbol
            )
        except EnvironmentError as error:
            try:
                status = State(str(error))
            except ValueError:
                status = State.BLOCKED_TESTER_DATA_ROOT
            raise Blocked(status) from None
        except (ValueError, OSError):
            raise Blocked(State.BLOCKED_TESTER_DATA_ROOT) from None
    try:
        return Environment.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError):
        raise Blocked(State.INITIALIZATION_FAILED) from None


def configuration_text(config: Configuration, expert: str, report: str, server: str) -> str:
    # Expert/report names originate solely from internal UUIDs; no user paths enter INI syntax.
    if not re.fullmatch(r"[a-f0-9]{32}", expert) or report != expert + ".htm":
        raise ValueError("INTERNAL_ID_REQUIRED")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", server):
        raise ValueError("INVALID_SERVER")
    settings = [
        "[Common]",
        f"Server={server}",
        "KeepPrivate=0",
        "NewsEnable=0",
        "[Experts]",
        "AllowLiveTrading=0",
        "AllowDllImport=0",
        "Enabled=0",
        "[StartUp]",
        "Expert=",
        "Script=",
        "[Tester]",
        f"Expert={expert}.ex5",
        f"Symbol={config.symbol}",
        f"Period={config.timeframe}",
        "Model=4",
        "Optimization=0",
        "ForwardMode=0",
        "UseLocal=1",
        "UseRemote=0",
        "UseCloud=0",
        "Visual=0",
        f"FromDate={config.from_date:%Y.%m.%d}",
        f"ToDate={config.to_date:%Y.%m.%d}",
        f"Deposit={config.initial_deposit}",
        f"Currency={config.currency}",
        f"Leverage=1:{config.leverage}",
        f"Report={report}",
        "ReplaceReport=0",
        "ShutdownTerminal=1",
    ]
    if config.set_text is not None:
        settings.append(f"ExpertParameters={expert}.set")
    return "\n".join(settings) + "\n"


class Adapter:
    def __init__(
        self,
        environment: Environment,
        process: Callable[[Path, list[str], Path, float, Event], Outcome] = execute,
    ) -> None:
        self.environment = environment
        self.process = process

    def prepare(
        self,
        config: Configuration,
        ea: bytes,
        expected_hash: str,
        root: Path,
        broker_name: str,
        cancel: Event,
    ) -> Path:
        env = self.environment
        if hashlib.sha256(ea).hexdigest() != expected_hash:
            raise Blocked(State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH)
        if env.broker_name != broker_name:
            raise Blocked(State.BLOCKED_SYMBOL)
        exe = env.terminal_executable.resolve()
        if (
            exe.name.lower() != "terminal64.exe"
            or not exe.is_file()
            or hashlib.sha256(exe.read_bytes()).hexdigest() != env.terminal_sha256
        ):
            raise Blocked(State.INITIALIZATION_FAILED)
        cache = env.cache_directory.resolve() / env.server
        if cache.resolve() != cache:
            raise Blocked(State.INITIALIZATION_FAILED)
        history, ticks = cache / "history" / config.symbol, cache / "ticks" / config.symbol
        # Validate exact cached symbol presence before launch; never substitute another symbol.
        if not history.is_dir() or not any(history.glob("*.hcc")):
            raise Blocked(State.BLOCKED_SYMBOL)
        if not ticks.is_dir() or not any(ticks.glob("*.tkc")):
            raise Blocked(State.BLOCKED_REAL_TICKS_UNAVAILABLE)
        runtime = root / "terminal"
        runtime.mkdir()  # unique run root; fail rather than overwrite or reuse
        deadline = time.monotonic() + min(config.timeout_seconds, 120)
        copied = 0
        sources = [exe, exe.parent / "metatester64.exe", *exe.parent.glob("*.dll")]
        destinations = [(p, runtime / p.name) for p in sources]
        for folder in (history, ticks):
            for path in folder.rglob("*"):
                if path.is_file():
                    if not path.resolve().is_relative_to(cache) or path.suffix.lower() not in {
                        ".hcc",
                        ".hcs",
                        ".tkc",
                    }:
                        raise Blocked(State.INITIALIZATION_FAILED)
                    destinations.append(
                        (path, runtime / "Bases" / env.server / path.relative_to(cache))
                    )
        symbols = cache / "symbols.raw"
        if not symbols.is_file():
            raise Blocked(State.BLOCKED_SYMBOL)
        destinations.append((symbols, runtime / "Bases" / env.server / "symbols.raw"))
        for source, target in destinations:
            if cancel.is_set():
                raise Blocked(State.CANCELLED)
            if time.monotonic() > deadline:
                raise Blocked(State.TIMEOUT)
            if source.is_symlink() or not source.is_file():
                raise Blocked(State.INITIALIZATION_FAILED)
            copied += source.stat().st_size
            if copied > 2 * 1024**3:
                raise Blocked(State.INITIALIZATION_FAILED)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        expert = config.baseline_run_id.hex
        ea_dir, set_dir = runtime / "MQL5" / "Experts", runtime / "MQL5" / "Profiles" / "Tester"
        ea_dir.mkdir(parents=True)
        set_dir.mkdir(parents=True)
        (ea_dir / (expert + ".ex5")).write_bytes(ea)
        if config.set_text is not None:
            (set_dir / (expert + ".set")).write_text(
                config.set_text, encoding="utf-8", newline="\n"
            )
        from trading_ecosystem.tester.environment import validate_config

        ini = configuration_text(config, expert, expert + ".htm", env.server)
        validate_config(ini, config, env.server)
        (root / "tester.ini").write_text(ini, encoding="utf-8", newline="\n")
        # Source accounts, charts, profiles, credentials and EA binaries are never copied.
        return runtime

    def run(self, config: Configuration, root: Path, runtime: Path, cancel: Event) -> Outcome:
        if (
            hashlib.sha256((runtime / "terminal64.exe").read_bytes()).hexdigest()
            != self.environment.terminal_sha256
        ):
            raise Blocked(State.INITIALIZATION_FAILED)
        return self.process(
            runtime / "terminal64.exe",
            ["/portable", "/config:" + str((root / "tester.ini").resolve())],
            runtime,
            float(config.timeout_seconds),
            cancel,
        )


def observed_failure(log: str) -> State | None:
    lower = log.lower()
    if re.search(r"invalid license|license (?:expired|invalid)|authorization failed", lower):
        return State.BLOCKED_LICENSE
    if re.search(r"tester (?:not allowed|prohibited)|testing (?:not allowed|prohibited)", lower):
        return State.BLOCKED_TESTER_ACCESS
    if re.search(r"initialization failed|oninit.*(?:failed|non-zero)", lower):
        return State.INITIALIZATION_FAILED
    if re.search(r"symbol.*(?:not found|unknown|unavailable)", lower):
        return State.BLOCKED_SYMBOL
    return None


def real_ticks_verified(log: str) -> bool:
    # Model=4 alone is not proof: MT5 may fall back to generated ticks. Unknown fails closed.
    percentages = re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)% real ticks", log, re.I)
    return (
        bool(percentages)
        and all(float(v) == 100 for v in percentages)
        and not re.search(
            r"real ticks (?:absent|unavailable)|generated ticks|tick generation|discarded",
            log,
            re.I,
        )
    )
