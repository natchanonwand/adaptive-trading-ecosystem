"""Terminal calibration boundaries; synthetic executables only."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from tests.phase5b_helpers import config
from trading_ecosystem.tester.adapter import Blocked, configuration_text, load_environment
from trading_ecosystem.tester.bootstrap import assess_probe, probe
from trading_ecosystem.tester.environment import (
    TerminalBinding,
    binding_status,
    readonly_compatibility,
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
    (data / "origin.txt").write_text(str(root), encoding="utf-16")
    (cache / "symbols").mkdir()
    (cache / "symbols" / "symbols-arbitrary.dat").write_bytes(b"opaque")
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
    with pytest.raises(Blocked, match="INITIALIZATION_FAILED"):
        load_environment(tmp_path / "environment.json")
    with pytest.raises(ValueError):
        TerminalBinding.model_validate(
            {**value.model_dump(), "password": "synthetic-value"}  # pragma: allowlist secret
        )


@pytest.mark.parametrize(
    "missing,reason",
    [
        ("terminal64.exe", "BLOCKED_TERMINAL_NOT_FOUND"),
        ("metatester64.exe", "BLOCKED_TERMINAL_NOT_FOUND"),
        ("profile/origin.txt", "BLOCKED_TESTER_DATA_ROOT"),
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
        assert not list(cwd.rglob("*.ex5"))
        assert "[Tester]" in (cwd / "bootstrap.ini").read_text()
        assert not (cwd / "Bases").exists()
        if failure:
            raise OSError("private native error must not escape")
        return Outcome(7)

    result = probe(value, tmp_path / "probe space", config(), fake)
    assert result["status"] == (
        "PROCESS_START_FAILED" if failure else "PROCESS_EXITED_DURING_BOOTSTRAP"
    )
    assert result["baseline_result"] is False
    assert historical.read_bytes() == original
    assert "private native" not in str(result)


def test_invalid_binding_never_launches(tmp_path: Path) -> None:
    value = binding(tmp_path)
    (value.terminal_data_root / "origin.txt").unlink()
    result = probe(value, tmp_path / "probe", config())
    assert result["status"] == "BLOCKED_TESTER_DATA_ROOT"
    assert result["process_created"] is False
    assert not (tmp_path / "probe").exists()


def test_bound_symbol_is_not_silently_replaced(tmp_path: Path) -> None:
    value = binding(tmp_path)
    evidence = {
        "scope": {"environment": "DEMO"},
        "latest": {
            "ACCOUNT:current": {
                "company": "Synthetic demo",
                "server": value.server,
                "trade_mode": 0,
            },
            "INSTRUMENT:XAUUSDm": {
                "broker_symbol": "XAUUSDm",
                "metadata": {"name": "XAUUSDm"},
                "status": "PARTIAL",
            },
        },
    }
    result = readonly_compatibility(value, evidence, "XAUUSDm")
    assert result["real_ticks_status"] == "UNKNOWN"
    assert result["current_symbol_status"] == "UNKNOWN"
    with pytest.raises(ValueError, match="BLOCKED_SYMBOL"):
        readonly_compatibility(value, evidence, "BTCUSDm")
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        readonly_compatibility(
            value.model_copy(update={"server": "Other-Demo"}), evidence, "XAUUSDm"
        )


def test_cache_layout_is_not_a_capability(tmp_path: Path) -> None:
    value = binding(tmp_path)
    for item in (value.terminal_data_root / "bases").rglob("*"):
        if item.is_file():
            item.unlink()
    assert validate_binding(value).terminal_build == "6230"
    (value.terminal_data_root / "origin.txt").write_text(str(tmp_path / "other"))
    with pytest.raises(ValueError, match="DATA_ROOT"):
        validate_binding(value)


def test_bounded_probe_preserves_all_source_bytes(tmp_path: Path) -> None:
    from threading import Event

    value = binding(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    def fake(exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event) -> Outcome:
        assert timeout == 10
        assert not list(cwd.rglob("*.dat"))
        assert "Optimization=0" in (cwd / "bootstrap.ini").read_text()
        return Outcome(1, timed_out=True)

    result = probe(value, tmp_path / "probes", config(), fake)
    assert result["status"] == "TIMEOUT"
    assert result["tester_initialized"] == "UNKNOWN"
    assert result["baseline_result"] is False
    runtime = Path(str(result["working_directory"]))
    assert (
        result["diagnostic_sha256"]
        == hashlib.sha256((runtime / "diagnostic.txt").read_bytes()).hexdigest()
    )
    assert all(p.read_bytes() == data for p, data in before.items())


def test_unwritable_runtime_never_launches(tmp_path: Path) -> None:
    value = binding(tmp_path)
    root = tmp_path / "occupied"
    root.write_bytes(b"not a directory")
    result = probe(value, root, config())
    assert result["status"] == "BLOCKED_TESTER_RUNTIME_DIRECTORY"
    assert result["process_created"] is False


def test_native_startup_is_not_tester_readiness() -> None:
    result = assess_probe(
        {"config_path": "probe.ini", "terminal_build": "6230", "timed_out": True},
        'successfully initialized from start config "probe.ini"\n'
        "MetaTrader 5 x64 build 6230 started for MetaQuotes Ltd.",
    )
    assert result["configuration_accepted"] == "OBSERVED"
    assert result["native_build_observed"] is True
    assert result["status"] == "TIMEOUT"
    assert assess_probe({}, "")["configuration_accepted"] == "UNKNOWN"


def test_binding_or_forged_success_cannot_enable_real_run(tmp_path: Path) -> None:
    value = binding(tmp_path)
    path = tmp_path / "terminal-binding.json"
    path.write_text(value.model_dump_json())
    assert binding_status(path)["status"] == "BOOTSTRAP_UNVERIFIED"
    record = {
        "terminal_binding_id": str(value.terminal_binding_id),
        "terminal_sha256": value.terminal_sha256,
        "kind": "ENVIRONMENT_BOOTSTRAP_PROBE",
        "baseline_result": False,
        "status": "READY",
    }
    observed = tmp_path / "native-bootstrap.json"
    observed.write_text(json.dumps(record))
    assert binding_status(path)["status"] == "BOOTSTRAP_UNVERIFIED"
    with pytest.raises(Blocked, match="INITIALIZATION_FAILED"):
        load_environment(tmp_path / "environment.json")
    record["status"] = "TIMEOUT"
    observed.write_text(json.dumps(record))
    assert binding_status(path)["status"] == "TIMEOUT"
    with pytest.raises(Blocked, match="TIMEOUT"):
        load_environment(tmp_path / "environment.json")
