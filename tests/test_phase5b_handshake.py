"""Native handshake evidence contracts; no real MT5 or candidate executions."""

import json
import sys
from pathlib import Path
from threading import Event
from typing import Any

import pytest

from tests.phase5b_helpers import config
from tests.test_phase5b_environment import binding
from trading_ecosystem.tester import handshake
from trading_ecosystem.tester.environment import binding_status
from trading_ecosystem.tester.process import execute


def records() -> list[dict[str, str]]:
    return [
        {
            "source": "logs/new.log",
            "component": "Startup",
            "message": 'successfully initialized from start config "probe.ini"',
        },
        {
            "source": "Tester/Agent/logs/new.log",
            "component": "Startup",
            "message": "MetaTester 5 x64 build 6230 (date)",
        },
        {
            "source": "Tester/Agent/logs/new.log",
            "component": "Server",
            "message": "MetaTester 5 started on 127.0.0.1:3000",
        },
        {
            "source": "Tester/Agent/logs/new.log",
            "component": "Startup",
            "message": "initialization finished",
        },
    ]


def processes() -> list[dict[str, Any]]:
    return [
        {"role": "terminal", "identity_verified": True},
        {"role": "tester", "identity_verified": True},
    ]


@pytest.mark.parametrize(
    "process_count,record_count,last",
    [
        (0, 4, "PROCESS_NOT_STARTED"),
        (1, 0, "PROCESS_STARTED"),
        (1, 1, "CONFIG_ACCEPTED"),
        (2, 1, "TESTER_SUBSYSTEM_STARTING"),
        (2, 3, "TESTER_SUBSYSTEM_STARTING"),
        (2, 4, "BOOTSTRAP_READY"),
    ],
)
def test_strict_stages(process_count: int, record_count: int, last: str) -> None:
    result = handshake.classify(
        processes()[:process_count],
        records()[:record_count],
        "probe.ini",
        "6230",
        "BOOTSTRAP_TIMEOUT",
        True,
    )
    assert result["stages"][-1] == last
    assert result["status"] == (
        "BOOTSTRAP_READY" if last == "BOOTSTRAP_READY" else "BOOTSTRAP_TIMEOUT"
    )
    assert result["real_tick_readiness"] == "UNKNOWN"


@pytest.mark.parametrize(
    "defect", ["child", "build", "source", "order", "config", "cleanup", "vague"]
)
def test_insufficient_evidence_never_ready(defect: str) -> None:
    ps, rs = processes(), records()
    if defect == "child":
        ps[1]["identity_verified"] = False
    if defect == "build":
        rs[1]["message"] = "MetaTester 5 x64 build 9999"
    if defect == "source":
        rs[3]["source"] = "Tester/other.log"
    if defect == "order":
        rs[2], rs[3] = rs[3], rs[2]
    if defect == "config":
        rs[0]["message"] = 'successfully initialized from start config "other.ini"'
    if defect == "vague":
        rs[3]["message"] = "not initialization finished"
    result = handshake.classify(
        ps, rs, "probe.ini", "6230", "BOOTSTRAP_TIMEOUT", defect != "cleanup"
    )
    assert result["status"] != "BOOTSTRAP_READY"


def test_exit_and_config_rejection() -> None:
    result = handshake.classify(
        processes()[:1], records()[:1], "probe.ini", "6230", "PROCESS_EXITED_DURING_BOOTSTRAP", True
    )
    assert result["status"] == "PROCESS_EXITED_DURING_BOOTSTRAP"
    rs = records()[:1]
    rs[0]["message"] = 'failed to initialize from start config "probe.ini"'
    assert (
        handshake.classify(processes(), rs, "probe.ini", "6230", "BOOTSTRAP_TIMEOUT", True)[
            "status"
        ]
        == "CONFIG_REJECTED"
    )


def test_sanitized_timestamped_journal(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "new.log").write_text(
        "AB\t0\t12:01:02.123\tStartup\tlogin=123456 account 765432 password=private\n"
        "AB\t0\t12:01:03.123\tStartup\taccount=765432\n",
        encoding="utf-16",
    )
    result = handshake.journal(tmp_path)
    assert len(result) == 1
    assert result[0]["native_time"] == "12:01:03.123"
    assert result[0]["captured_at"]
    assert "765432" not in str(result)
    assert "private" not in str(result)
    assert "123456" not in handshake.sanitize("login=123456")


def test_exclusive_fixed_window_preserves_previous_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = tmp_path / "previous.json"
    old.write_bytes(b'{"status":"TIMEOUT"}')
    value = binding(tmp_path)
    calls = []

    def fake(*args: Any, **kwargs: Any) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "status": "PROCESS_START_FAILED",
            "baseline_result": False,
            "candidate_staged": False,
        }

    monkeypatch.setattr(handshake, "probe", fake)
    root = tmp_path / "new"
    result = handshake.run_handshake(value, root, config(timeout_seconds=600))
    assert result["status"] == "PROCESS_START_FAILED"
    assert result["baseline_result"] is False and result["candidate_staged"] is False
    assert calls == [{"window_seconds": 45.0}]
    with pytest.raises(FileExistsError):
        handshake.run_handshake(value, root, config())
    assert len(calls) == 1
    assert old.read_bytes() == b'{"status":"TIMEOUT"}'
    assert (
        json.loads((root / "preregistration.json").read_bytes())["baseline_timeout_seconds"] == 600
    )


def test_new_observation_does_not_rewrite_previous_timeout(tmp_path: Path) -> None:
    value = binding(tmp_path)
    path = tmp_path / "terminal-binding.json"
    path.write_text(value.model_dump_json())
    old = tmp_path / "native-bootstrap.json"
    old.write_text(json.dumps({"status": "TIMEOUT"}))
    before = old.read_bytes()
    (tmp_path / "native-handshake.json").write_text(
        json.dumps(
            {
                "schema": "PHASE5B1C_HANDSHAKE_V1",
                "terminal_binding_id": str(value.terminal_binding_id),
                "terminal_sha256": value.terminal_sha256,
                "baseline_result": False,
                "status": "BOOTSTRAP_TIMEOUT",
                "probe_id": "synthetic-probe",
            }
        )
    )
    result = binding_status(path)
    assert result["status"] == "BOOTSTRAP_TIMEOUT"
    assert result["last_probe"] == "synthetic-probe"
    assert old.read_bytes() == before


def test_native_lifecycle_observer_on_harmless_python_process(tmp_path: Path) -> None:
    observer = handshake.Observer(tmp_path)
    try:
        outcome = execute(
            Path(sys.executable),
            ["-c", "import time; time.sleep(0.3)"],
            tmp_path,
            3,
            Event(),
            observer,
        )
        assert outcome.code == 0
        root = next(p for p in observer.processes.values() if p["role"] == "terminal")
        assert root["parent_pid"] > 0 and root["pid"] > 0
        assert root["start_time"] and root["end_time"]
        assert root["exit_code"] == 0
        assert root["identity_verified"] is False
    finally:
        observer.close()
