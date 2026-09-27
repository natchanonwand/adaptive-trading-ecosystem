"""Boundary, normalization and actual Windows child ownership checks (no MT5 execution)."""

import hashlib
import json
import sys
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from tests.phase5b_helpers import EA, config, environment, report
from trading_ecosystem.tester.adapter import (
    Adapter,
    Blocked,
    configuration_text,
    observed_failure,
    real_ticks_verified,
)
from trading_ecosystem.tester.contracts import Configuration, State, transition
from trading_ecosystem.tester.evidence import finalize, safe_log
from trading_ecosystem.tester.parser import numeric, parse
from trading_ecosystem.tester.process import execute


@pytest.mark.parametrize(
    "change",
    [
        {"from_date": "2026-09-08"},
        {"to_date": "2025-01-01"},
        {"from_date": "2020-01-01"},
        {"to_date": "2099-01-01"},
        {"initial_deposit": "0"},
        {"initial_deposit": "NaN"},
        {"initial_deposit": "1.001"},
        {"timeframe": "H2"},
        {"symbol": "XAUUSDm\nOptimization=1"},
        {"environment": "LIVE"},
        {"environment": "DEMO"},
        {"tester_model": "OPEN_PRICES"},
        {"timeout_seconds": 0},
        {"timeout_seconds": True},
        {"timeout_seconds": 3601},
        {"leverage": 0},
        {"currency": "EUR"},
        {"input_provenance": "USER_SET"},
        {"set_text": "Lots=0.01"},
        {"input_provenance": "USER_SET", "set_text": "Lots=1||1||1||2||Y"},
        {"input_provenance": "USER_SET", "set_text": "; password=synthetic"},
        {"input_provenance": "USER_SET", "set_text": "../x=1"},
    ],
)
def test_configuration_rejects_unsafe_values(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        config(**change)


def test_explicit_input_identity_and_ini() -> None:
    cfg = config(input_provenance="USER_SET", set_text="Lots=0.01||0.01||0.01||1||N")
    assert Configuration.model_validate_json(cfg.model_dump_json()) == cfg
    ini = configuration_text(
        cfg, cfg.baseline_run_id.hex, cfg.baseline_run_id.hex + ".htm", "Synthetic-Demo"
    )
    for value in (
        "Model=4",
        "Optimization=0",
        "UseCloud=0",
        "UseRemote=0",
        "AllowLiveTrading=0",
        "AllowDllImport=0",
        "ReplaceReport=0",
        "ShutdownTerminal=1",
    ):
        assert value in ini.splitlines()
    assert "Login=" not in ini and "Password=" not in ini
    with pytest.raises(ValueError):
        configuration_text(cfg, "../x", "x.htm", "s")


def test_state_finality() -> None:
    state = State.READY
    for target in (State.QUEUED, State.PREPARING, State.RUNNING, State.PARSING, State.COMPLETE):
        state = transition(state, target)
    for final in (State.COMPLETE, State.TIMEOUT, State.CANCELLED, State.BLOCKED_LICENSE):
        with pytest.raises(ValueError):
            transition(final, State.QUEUED)
    with pytest.raises(ValueError):
        transition(State.RUNNING, State.COMPLETE)


def test_realistic_report_determinism_and_utf16() -> None:
    ids = (uuid4(), uuid4(), uuid4())
    raw = report(ids[0].hex)
    result = parse(raw, *ids)
    assert result == parse(raw, *ids)
    assert result.report_identity == hashlib.sha256(raw).hexdigest()
    assert result.metrics["net_profit"] == "250.50"
    assert result.metrics["win_rate"] == "0.6"
    assert result.metrics["total_trades"] == 10
    assert result.metrics["maximum_consecutive_losses"] == 2
    assert result.metrics["balance_drawdown"] == "120.00 (1.20%)"
    assert result.metadata["Build"] == "UNAVAILABLE"
    assert parse(raw.decode().encode("utf-16"), *ids).metrics == result.metrics
    assert parse(raw + b"\n", *ids).result_identity != result.result_identity


def test_optional_missing_fields_are_not_zero() -> None:
    raw = (
        b"<table><tr><td>Expert:</td><td>fixture</td><td>Symbol:</td><td>XAUUSDm</td>"
        b"<td>Period:</td><td>H1</td></tr><tr><td>Total Net Profit:</td><td>0</td>"
        b"<td>Total Trades:</td><td>0</td></tr></table>"
    )
    result = parse(raw, uuid4(), uuid4(), uuid4())
    assert result.metrics["win_rate"] is None
    assert "profit_factor" in result.unavailable
    assert result.metrics["gross_profit"] is None


@pytest.mark.parametrize(
    "old,new",
    [
        ("250.50", "250,50"),
        ("6 (60.00%)", "9 (60.00%)"),
        ("02:30:00", "02:90:00"),
        ("120.00 (1.20%)", "120,00 (1,20%)"),
        ("4 (50.00%)", "7 (50.00%)"),
        ("Total Net Profit:", "Missing:"),
    ],
)
def test_malformed_reports_fail(old: str, new: str) -> None:
    with pytest.raises(ValueError):
        parse(report("fixture").replace(old.encode(), new.encode()), uuid4(), uuid4(), uuid4())


@pytest.mark.parametrize("value", ["1,00", "1.000,50", "NaN", "inf", "1 00.50"])
def test_ambiguous_numbers_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        numeric(value)


def test_grouped_numbers() -> None:
    assert numeric("1,234.50") == numeric("1 234.50") == numeric("1234.50")


@pytest.mark.parametrize(
    "log,expected",
    [
        ("100% real ticks", True),
        ("99.9% real ticks", False),
        ("Model=4", False),
        ("100% real ticks; generated ticks", False),
        ("100% real ticks\n0% real ticks", False),
    ],
)
def test_real_ticks_must_be_observed(log: str, expected: bool) -> None:
    assert real_ticks_verified(log) is expected


@pytest.mark.parametrize(
    "log,state",
    [
        ("invalid license", State.BLOCKED_LICENSE),
        ("testing prohibited", State.BLOCKED_TESTER_ACCESS),
        ("OnInit failed", State.INITIALIZATION_FAILED),
        ("symbol not found", State.BLOCKED_SYMBOL),
    ],
)
def test_observed_restrictions(log: str, state: State) -> None:
    assert observed_failure(log) == state


def test_staging_preserves_sources_and_omits_private_profiles(tmp_path: Path) -> None:
    env = environment(tmp_path)
    (env.terminal_executable.parent / "accounts.dat").write_bytes(b"private fixture")
    cfg = config()
    root = tmp_path / "run"
    root.mkdir()
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    runtime = Adapter(env).prepare(
        cfg, EA, hashlib.sha256(EA).hexdigest(), root, "Synthetic demo", threading.Event()
    )
    assert (runtime / "MQL5/Experts" / (cfg.baseline_run_id.hex + ".ex5")).read_bytes() == EA
    assert not list(runtime.rglob("accounts.dat"))
    assert all(Path(p).read_bytes() == v for p, v in before.items())
    with pytest.raises(FileExistsError):
        Adapter(env).prepare(
            cfg, EA, hashlib.sha256(EA).hexdigest(), root, "Synthetic demo", threading.Event()
        )


@pytest.mark.parametrize(
    "problem,state",
    [
        ("sha", State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH),
        ("symbol", State.BLOCKED_SYMBOL),
        ("ticks", State.BLOCKED_REAL_TICKS_UNAVAILABLE),
        ("terminal", State.INITIALIZATION_FAILED),
    ],
)
def test_staging_fail_closed(tmp_path: Path, problem: str, state: State) -> None:
    env = environment(tmp_path)
    cfg = config(symbol="BTCUSDm") if problem == "symbol" else config()
    if problem == "ticks":
        (env.cache_directory / env.server / "ticks/XAUUSDm/202609.tkc").unlink()
    if problem == "terminal":
        env.terminal_executable.write_bytes(b"changed")
    with pytest.raises(Blocked) as exc:
        Adapter(env).prepare(
            cfg,
            EA,
            "0" * 64 if problem == "sha" else hashlib.sha256(EA).hexdigest(),
            tmp_path,
            "Synthetic demo",
            threading.Event(),
        )
    assert exc.value.status == state


def test_safe_logs_and_append_only_manifest(tmp_path: Path) -> None:
    text = "normal\r\nreport\n"
    assert safe_log(text) == text
    assert "sensitive" not in safe_log("password=sensitive\r\nnormal\n")
    (tmp_path / "raw.htm").write_bytes(b"fixture")
    identity = finalize(tmp_path, "COMPLETE")
    assert json.loads((tmp_path / "manifest.json").read_text())["identity"] == identity
    with pytest.raises(FileExistsError):
        finalize(tmp_path, "COMPLETE")


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_process_requires_finite_timeout(tmp_path: Path, timeout: float) -> None:
    with pytest.raises(ValueError):
        execute(Path(sys.executable), [], tmp_path, timeout, threading.Event())


def test_windows_arguments_no_shell(tmp_path: Path) -> None:
    argument = 'literal & whoami | $(test) "quote" \\ path'
    script = "import pathlib,sys; pathlib.Path('args.txt').write_text(sys.argv[1])"
    outcome = execute(
        Path(sys.executable), ["-c", script, argument], tmp_path, 10, threading.Event()
    )
    assert outcome.code == 0
    assert (tmp_path / "args.txt").read_text() == argument


@pytest.mark.parametrize("cancelled", [False, True])
def test_windows_timeout_and_cancel(tmp_path: Path, cancelled: bool) -> None:
    cancel = threading.Event()
    if cancelled:
        cancel.set()
    outcome = execute(
        Path(sys.executable), ["-c", "import time; time.sleep(30)"], tmp_path, 0.2, cancel
    )
    assert outcome.cancelled == cancelled
    assert outcome.timed_out != cancelled


def test_windows_owned_descendants_die_with_root(tmp_path: Path) -> None:
    child = (
        "import pathlib,time; pathlib.Path('child-ready').touch(); "
        "time.sleep(2); pathlib.Path('escaped').touch()"
    )
    parent = (
        "import pathlib,subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{child!r}]); "
        "\nwhile not pathlib.Path('child-ready').exists(): time.sleep(0.01)"
    )
    outcome = execute(Path(sys.executable), ["-c", parent], tmp_path, 10, threading.Event())
    assert outcome.code == 0 and (tmp_path / "child-ready").exists()
    threading.Event().wait(2.5)
    assert not (tmp_path / "escaped").exists()


def test_external_child_does_not_inherit_application_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TE_DATABASE_URL", "synthetic-private-value")
    script = "import os,sys; sys.exit(1 if 'TE_DATABASE_URL' in os.environ else 0)"
    assert execute(Path(sys.executable), ["-c", script], tmp_path, 10, threading.Event()).code == 0
