"""Terminal calibration boundaries; synthetic executables only."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from tests.phase5b_helpers import config
from trading_ecosystem.tester.adapter import configuration_text, load_environment
from trading_ecosystem.tester.bootstrap import probe
from trading_ecosystem.tester.environment import (
    TerminalBinding,
    select_terminal,
    validate_binding,
    validate_config,
)
from trading_ecosystem.tester.process import Outcome


def binding(root: Path) -> TerminalBinding:
    exe = root / "terminal64.exe"
    exe.write_bytes(b"synthetic terminal")
    (root / "metatester64.exe").write_bytes(b"synthetic tester")
    data = root / "profile"
    cache = data / "bases" / "Synthetic-Demo"
    cache.mkdir(parents=True)
    (cache / "symbols.raw").write_bytes(b"symbols")
    for folder, filename in (("history", "2026.hcc"), ("ticks", "202601.tkc")):
        target = cache / folder / "XAUUSDm"
        target.mkdir(parents=True)
        (target / filename).write_bytes(b"synthetic cache")
    return TerminalBinding(
        terminal_binding_id=uuid4(),
        terminal_executable=exe,
        terminal_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        terminal_data_root=data,
        company="Synthetic",
        product="Synthetic",
        terminal_build="6230",
        discovery_source="INSTALLED_TERMINAL_ORIGIN_MAPPING",
        verified_at=datetime.now(UTC),
        broker_name="Synthetic demo",
        server="Synthetic-Demo",
    )


def test_valid_pinned_terminal_and_build(tmp_path: Path) -> None:
    value = binding(tmp_path)
    env = validate_binding(value)
    assert env.terminal_build == "6230"
    assert env.cache_directory == value.terminal_data_root / "bases"
    (tmp_path / "terminal-binding.json").write_text(value.model_dump_json(), encoding="utf-8")
    assert load_environment(tmp_path / "environment.json") == env
    with pytest.raises(ValueError):
        TerminalBinding.model_validate(
            {**value.model_dump(), "password": "synthetic-value"}  # pragma: allowlist secret
        )


@pytest.mark.parametrize(
    "missing,reason",
    [
        ("terminal64.exe", "BLOCKED_TERMINAL_NOT_FOUND"),
        ("profile/bases/Synthetic-Demo/symbols.raw", "BLOCKED_TESTER_CACHE"),
        ("profile/bases/Synthetic-Demo/history/XAUUSDm/2026.hcc", "BLOCKED_TESTER_CACHE"),
        ("profile/bases/Synthetic-Demo/ticks/XAUUSDm/202601.tkc", "BLOCKED_TESTER_CACHE"),
    ],
)
def test_missing_files(tmp_path: Path, missing: str, reason: str) -> None:
    value = binding(tmp_path)
    (tmp_path / missing).unlink()
    with pytest.raises(ValueError, match=reason):
        validate_binding(value)


def test_wrong_identity_and_data_root(tmp_path: Path) -> None:
    value = binding(tmp_path)
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        validate_binding(value.model_copy(update={"terminal_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="DATA_ROOT"):
        validate_binding(value.model_copy(update={"terminal_data_root": tmp_path / "missing"}))
    with pytest.raises(ValueError, match="UNSAFE_TERMINAL_PATH"):
        validate_binding(value.model_copy(update={"terminal_executable": Path("relative.exe")}))


def test_discovery_never_selects_first_terminal(tmp_path: Path) -> None:
    value = binding(tmp_path)
    origin = tmp_path / "profiles" / "one"
    origin.mkdir(parents=True)
    (origin / "origin.txt").write_text(str(tmp_path), encoding="utf-16")
    assert select_terminal([value.terminal_executable], origin.parent) == (
        value.terminal_executable,
        origin,
    )
    with pytest.raises(ValueError, match="NOT_FOUND"):
        select_terminal([], origin.parent)
    other = tmp_path / "other.exe"
    other.write_bytes(b"other")
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        select_terminal([value.terminal_executable, other], origin.parent)


@pytest.mark.parametrize(
    "change", ["Model=0", "Optimization=1", "Deposit=1", "Period=M5", "Expert=other.ex5"]
)
def test_invalid_generated_config(tmp_path: Path, change: str) -> None:
    cfg = config()
    text = configuration_text(
        cfg, cfg.baseline_run_id.hex, cfg.baseline_run_id.hex + ".htm", "Synthetic-Demo"
    )
    validate_config(text, cfg, "Synthetic-Demo")
    key = change.split("=")[0]
    lines = [change if line.startswith(key + "=") else line for line in text.splitlines()]
    with pytest.raises(ValueError, match="CONFIG_INVALID"):
        validate_config("\n".join(lines), cfg, "Synthetic-Demo")


@pytest.mark.parametrize("failure", [True, False])
def test_probe_process_boundary(tmp_path: Path, failure: bool) -> None:
    from threading import Event

    value = binding(tmp_path)
    historical = tmp_path / "failed-run.json"
    historical.write_bytes(b'{"status":"INITIALIZATION_FAILED"}')
    original = historical.read_bytes()

    def fake(exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event) -> Outcome:
        assert isinstance(args, list) and args[0] == "/portable" and timeout == 10
        assert not (cwd / "MQL5").exists()
        assert "[Tester]" not in (cwd / "bootstrap.ini").read_text()
        if failure:
            raise OSError("private native error must not escape")
        return Outcome(7)

    result = probe(value, tmp_path / "probe space", fake)
    assert result["status"] == (
        "PROCESS_START_FAILED" if failure else "PROCESS_EXITED_DURING_BOOTSTRAP"
    )
    assert result["baseline_result"] is False
    assert historical.read_bytes() == original
    assert "private native" not in str(result)


def test_probe_cache_blocker_never_launches(tmp_path: Path) -> None:
    value = binding(tmp_path)
    (value.terminal_data_root / "bases/Synthetic-Demo/symbols.raw").unlink()
    result = probe(value, tmp_path / "probe")
    assert result["status"] == "BLOCKED_TESTER_CACHE"
    assert result["process_created"] is False
    assert not (tmp_path / "probe").exists()


def test_bound_symbol_is_not_silently_replaced(tmp_path: Path) -> None:
    value = binding(tmp_path)
    cache = value.terminal_data_root / "bases" / value.server
    for folder in ("history", "ticks"):
        (cache / folder / "XAUUSDm").rename(cache / folder / "BTCUSDm")
    (tmp_path / "terminal-binding.json").write_text(value.model_dump_json(), encoding="utf-8")
    assert load_environment(tmp_path / "environment.json", "BTCUSDm").server == value.server
    with pytest.raises(ValueError, match="CACHE"):
        validate_binding(value, "XAUUSDm")
