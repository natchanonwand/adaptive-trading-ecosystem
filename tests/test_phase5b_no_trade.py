"""Fixed-source diagnostic safety and synthetic compiler/native-marker contracts."""

import hashlib
from pathlib import Path
from threading import Event
from typing import Any
from uuid import uuid4

import pytest

from tests.phase5b_helpers import config
from tests.test_phase5b_environment import binding
from tests.test_phase5b_handshake import processes
from trading_ecosystem.tester import no_trade
from trading_ecosystem.tester.process import Outcome


def test_fixed_reviewable_source_identity_and_no_writes() -> None:
    source = no_trade.fixed_source()
    assert hashlib.sha256(source).hexdigest() == no_trade.SOURCE_SHA
    for forbidden in (
        b"OrderSend",
        b"CTrade",
        b"PositionOpen",
        b"PositionClose",
        b"WebRequest",
        b"#include",
        b"#import",
        b"FileOpen",
        b"Socket",
        b"input ",
    ):
        assert forbidden not in source
    assert b"MQL_TESTER" in source and b"MQL_OPTIMIZATION" in source
    assert source.count(b"TesterStop();") == 1
    assert b"if(first_tick_seen)" in source


def test_account_blocker_is_not_candidate_license_denial() -> None:
    cfg = config()
    rs = [
        {
            "source": "Tester/new.log",
            "component": "Tester",
            "message": "tester not started because the account is not specified",
        },
        {
            "source": "logs/new.log",
            "component": "MQL5.community",
            "message": "authorization failed",
        },
    ]
    result = no_trade.marker_assessment(
        processes(), rs, cfg, "probe.ini", "6230", "PROCESS_EXITED_DURING_BOOTSTRAP", True, False
    )
    assert result["native_blocker"] == "TESTER_ACCOUNT_NOT_SPECIFIED"
    assert result["status"] == "PROCESS_EXITED_DURING_BOOTSTRAP"
    assert not result["probe_init_succeeded"]


@pytest.mark.parametrize("case", ["success", "failure", "missing", "wrong_build", "timeout"])
def test_compilation_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    value = binding(tmp_path)
    if case != "missing":
        (tmp_path / "metaeditor64.exe").write_bytes(b"synthetic compiler")
    monkeypatch.setattr(
        no_trade,
        "file_identity",
        lambda _: {
            "company": value.company,
            "product": "MetaEditor",
            "build": "9999" if case == "wrong_build" else value.terminal_build,
        },
    )

    def fake(exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event) -> Outcome:
        assert timeout == no_trade.COMPILER_SECONDS
        assert args[0] == "/portable" and args[-1] == "/log"
        assert (cwd / "Phase5BNoTradeProbe.mq5").read_bytes() == no_trade.fixed_source()
        (cwd / "Phase5BNoTradeProbe.ex5").write_bytes(b"synthetic compiled probe")
        (cwd / "Phase5BNoTradeProbe.log").write_text(
            "Result: 1 errors, 0 warnings"
            if case == "failure"
            else "Result: 0 errors, 0 warnings, time",
            encoding="utf-16",
        )
        return Outcome(0, timed_out=case == "timeout")

    result = no_trade.compile_probe(value, tmp_path / "compile", fake)
    if case == "success":
        assert result["status"] == "COMPILED"
        assert result["ex5_sha256"] == hashlib.sha256(b"synthetic compiled probe").hexdigest()
    elif case in {"missing", "wrong_build"}:
        assert result["status"] == "BLOCKED_PROBE_COMPILER_UNAVAILABLE"
    else:
        assert result["status"] == "PROBE_COMPILATION_FAILED"
    assert not (tmp_path / "Phase5BNoTradeProbe.ex5").exists()


@pytest.mark.parametrize(
    "markers,expected",
    [
        ([], "PROCESS_EXITED_DURING_BOOTSTRAP"),
        (["PHASE5B_PROBE_INIT_OK"], "TESTER_INITIALIZED"),
        (["PHASE5B_PROBE_FIRST_TICK"], "PROCESS_EXITED_DURING_BOOTSTRAP"),
        (["PHASE5B_PROBE_INIT_OK", "PHASE5B_PROBE_FIRST_TICK"], "TESTER_INITIALIZED"),
        (
            ["PHASE5B_PROBE_INIT_OK", "PHASE5B_PROBE_FIRST_TICK", "PHASE5B_PROBE_DEINIT:1"],
            "BOOTSTRAP_READY",
        ),
    ],
)
def test_marker_stages(markers: list[str], expected: str) -> None:
    cfg = config()
    records = [
        {
            "source": "logs/new.log",
            "component": "Startup",
            "message": 'successfully initialized from start config "probe.ini"',
        }
    ]
    records += [
        {
            "source": "Tester/Agent/logs/new.log",
            "component": f"{cfg.baseline_run_id.hex} ({cfg.symbol},{cfg.timeframe})",
            "message": m,
        }
        for m in markers
    ]
    result = no_trade.marker_assessment(
        processes(),
        records,
        cfg,
        "probe.ini",
        "6230",
        "PROCESS_EXITED_DURING_BOOTSTRAP",
        True,
        True,
    )
    assert result["status"] == expected
    assert result["full_interval_real_ticks"] == "UNKNOWN"


@pytest.mark.parametrize(
    "defect", ["unrelated_expert", "unrelated_log", "no_process", "bad_exit", "cleanup"]
)
def test_false_positive_markers_rejected(defect: str) -> None:
    cfg = config()
    ps = processes() if defect != "no_process" else []
    rs = [
        {
            "source": "logs/new.log",
            "component": "Startup",
            "message": 'successfully initialized from start config "probe.ini"',
        }
    ]
    for m in ["PHASE5B_PROBE_INIT_OK", "PHASE5B_PROBE_FIRST_TICK", "PHASE5B_PROBE_DEINIT:1"]:
        rs.append(
            {
                "source": "logs/new.log"
                if defect == "unrelated_log"
                else "Tester/Agent/logs/new.log",
                "component": "Other EA"
                if defect == "unrelated_expert"
                else f"{cfg.baseline_run_id.hex} ({cfg.symbol},{cfg.timeframe})",
                "message": m,
            }
        )
    result = no_trade.marker_assessment(
        ps,
        rs,
        cfg,
        "probe.ini",
        "6230",
        "BOOTSTRAP_TIMEOUT",
        defect != "cleanup",
        defect != "bad_exit",
    )
    assert result["status"] != "BOOTSTRAP_READY"


def test_tampered_source_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(no_trade, "SOURCE_SHA", "0" * 64)
    with pytest.raises(ValueError, match="FIXED_PROBE_SOURCE_CHANGED"):
        no_trade.fixed_source()


def test_compilation_never_accepts_a_stale_or_missing_binary(tmp_path: Path) -> None:
    path = tmp_path / "missing.ex5"
    assert not no_trade.compilation_valid(Outcome(0), "Result: 0 errors, 0 warnings", path)
    path.write_bytes(b"old")
    assert not no_trade.compilation_valid(Outcome(2), "Result: 0 errors, 0 warnings", path)
    assert no_trade.compilation_valid(Outcome(1), "Result: 0 errors, 0 warnings", path)
    assert not no_trade.compilation_valid(Outcome(0), "Result: 1 errors, 0 warnings", path)


def test_isolated_staging_once_without_baseline_or_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = binding(tmp_path)
    root = tmp_path / "diagnostic"
    compiler = root / "compiler"
    compiler.mkdir(parents=True)
    (compiler / "Phase5BNoTradeProbe.mq5").write_bytes(no_trade.fixed_source())
    binary = compiler / "Phase5BNoTradeProbe.ex5"
    binary.write_bytes(b"synthetic fixed probe")
    compiled = {
        "status": "COMPILED",
        "source_sha256": no_trade.SOURCE_SHA,
        "ex5_path": str(binary),
        "ex5_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }
    cfg = config()
    before = cfg.model_dump_json()
    old = tmp_path / "old-probe.json"
    old.write_bytes(b'{"status":"TIMEOUT"}')
    identity = uuid4()
    calls = []

    def fake(
        exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event, observer: Any = None
    ) -> Outcome:
        calls.append(timeout)
        experts = list((cwd / "MQL5/Experts").glob("*.ex5"))
        assert len(experts) == 1 and experts[0].stem == identity.hex
        assert experts[0].read_bytes() == binary.read_bytes()
        assert not (cwd / "MQL5/Experts" / (cfg.baseline_run_id.hex + ".ex5")).exists()
        assert not (cwd / "Bases").exists()
        return Outcome(0)

    monkeypatch.setattr(no_trade, "execute", fake)
    result = no_trade._execute_compiled(value, root, cfg, compiled, identity)
    assert calls == [60.0]
    assert result["baseline_result"] is False and result["candidate_staged"] is False
    assert result["status"] != "BOOTSTRAP_READY"
    assert cfg.model_dump_json() == before
    assert old.read_bytes() == b'{"status":"TIMEOUT"}'
    with pytest.raises(FileExistsError):
        no_trade._execute_compiled(value, root, cfg, compiled, identity)
    assert calls == [60.0]
    outside = tmp_path / "external.ex5"
    outside.write_bytes(b"external code")
    with pytest.raises(ValueError, match="FIXED_COMPILED_PROBE_REQUIRED"):
        no_trade._execute_compiled(
            value, root, cfg, {**compiled, "ex5_path": str(outside)}, uuid4()
        )
