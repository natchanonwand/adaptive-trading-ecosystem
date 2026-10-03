"""DEMO identity, disclosure and ephemeral native materialization contracts."""

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from tests.phase5b_helpers import config
from tests.test_phase5b_environment import binding
from trading_ecosystem.tester import account_probe
from trading_ecosystem.tester.account_probe import capture_logs, ephemeral_ini, log_positions
from trading_ecosystem.tester.adapter import configuration_text
from trading_ecosystem.tester.process import Outcome
from trading_ecosystem.tester.research_account import AccountBlocked, account_config, assess


def records(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {
            "path": str(root),
            "data_path": str(root / "profile"),
            "build": 6230,
            "connected": True,
            "trade_allowed": False,
        },
        {
            "company": "Exness Technologies Ltd",
            "server": "Synthetic-Demo",
            "trade_mode": 0,
            "login": 123456789,
        },
    )


def test_demo_binding_contains_only_safe_metadata(tmp_path: Path) -> None:
    pinned = binding(tmp_path)
    terminal, account = records(tmp_path)
    account.update(
        password="synthetic-sensitive-value",  # pragma: allowlist secret
        token="synthetic-token",  # pragma: allowlist secret
    )
    context = assess(pinned, terminal, account, 42)
    encoded = context.binding.model_dump_json()
    assert context.binding.environment_classification == "DEMO"
    assert context.binding.terminal_binding_id == pinned.terminal_binding_id
    for forbidden in (str(account["login"]), "synthetic-sensitive-value", "synthetic-token"):
        assert forbidden not in encoded and forbidden not in repr(context)
    assert set(json.loads(encoded)) == {
        "account_binding_id",
        "terminal_binding_id",
        "company",
        "server",
        "environment_classification",
        "account_fingerprint",
        "verified_at",
        "discovery_source",
    }
    assert assess(pinned, terminal, account, 42).binding.account_fingerprint != (
        context.binding.account_fingerprint
    )


@pytest.mark.parametrize(
    "field,value,status",
    [
        ("trade_mode", None, "BLOCKED_TESTER_ACCOUNT_NOT_DEMO"),
        ("trade_mode", 2, "BLOCKED_TESTER_ACCOUNT_NOT_DEMO"),
        ("trade_mode", 1, "BLOCKED_TESTER_ACCOUNT_NOT_DEMO"),
        ("trade_mode", False, "BLOCKED_TESTER_ACCOUNT_NOT_DEMO"),
        ("server", "Other-Demo", "BLOCKED_TESTER_ACCOUNT_SERVER_MISMATCH"),
        ("company", "Other", "BLOCKED_TESTER_ACCOUNT_SERVER_MISMATCH"),
        ("login", None, "BLOCKED_TESTER_ACCOUNT_UNBOUND"),
        ("login", 0, "BLOCKED_TESTER_ACCOUNT_UNBOUND"),
    ],
)
def test_account_rejections(tmp_path: Path, field: str, value: Any, status: str) -> None:
    pinned = binding(tmp_path)
    terminal, account = records(tmp_path)
    account[field] = value
    with pytest.raises(AccountBlocked, match=status):
        assess(pinned, terminal, account, 42)


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "C:/unrelated"),
        ("data_path", "C:/unrelated"),
        ("build", 9999),
    ],
)
def test_profile_identity_required(tmp_path: Path, field: str, value: Any) -> None:
    pinned = binding(tmp_path)
    terminal, account = records(tmp_path)
    terminal[field] = value
    with pytest.raises(AccountBlocked, match="BLOCKED_TERMINAL_IDENTITY_MISMATCH"):
        assess(pinned, terminal, account, 42)


@pytest.mark.parametrize("case", ["missing", "disconnected", "autotrading"])
def test_unavailable_context(tmp_path: Path, case: str) -> None:
    pinned = binding(tmp_path)
    terminal, account = records(tmp_path)
    if case == "disconnected":
        terminal["connected"] = False
    if case == "autotrading":
        terminal["trade_allowed"] = True
    with pytest.raises(AccountBlocked, match="BLOCKED_TESTER_ACCOUNT_CONTEXT_UNAVAILABLE"):
        assess(pinned, terminal, None if case == "missing" else account, 42)


@pytest.mark.parametrize("fail", [False, True])
def test_ephemeral_identifier_and_cleanup(tmp_path: Path, fail: bool) -> None:
    pinned = binding(tmp_path)
    context = assess(pinned, *records(tmp_path), 42)
    cfg = config()
    before = cfg.model_dump_json()
    base = configuration_text(
        cfg, cfg.baseline_run_id.hex, cfg.baseline_run_id.hex + ".htm", pinned.server
    )
    path = tmp_path / "probe.ini"
    try:
        with ephemeral_ini(path, base, context):
            text = path.read_text()
            assert text == base.replace("[Common]\n", "[Common]\nLogin=123456789\n")
            assert "Password=" not in text
            assert "AllowLiveTrading=0" in text and "Enabled=0" in text
            if fail:
                raise RuntimeError("synthetic interruption")
    except RuntimeError:
        assert fail
    assert not path.exists()
    assert cfg.model_dump_json() == before
    with pytest.raises(ValueError):
        account_config(base + "Login=5", context)


def test_only_fresh_logs_captured_and_redacted(tmp_path: Path) -> None:
    root = tmp_path / "native"
    root.mkdir()
    source = root / "today.log"
    source.write_text("old evidence\n", encoding="utf-16")
    roots = {"logs": root}
    offsets = log_positions(roots)
    original = source.read_bytes()
    with source.open("ab") as stream:
        stream.write("new 123456789\npassword=synthetic\n".encode("utf-16-le"))
    capture_logs(roots, offsets, tmp_path / "safe", 123456789)
    safe = (tmp_path / "safe/logs/today.log").read_text()
    assert "old evidence" not in safe and "123456789" not in safe and "synthetic" not in safe
    assert "[ACCOUNT_REDACTED]" in safe
    assert source.read_bytes().startswith(original)


def test_ephemeral_refuses_to_replace_existing_evidence(tmp_path: Path) -> None:
    pinned = binding(tmp_path)
    context = assess(pinned, *records(tmp_path), 42)
    path = tmp_path / "existing.ini"
    path.write_text("original")
    with pytest.raises(FileExistsError), ephemeral_ini(path, "[Common]\n", context):
        pytest.fail("must never yield")
    assert path.read_text() == "original"


def test_generated_report_cleanup_preserves_unrelated_files(tmp_path: Path) -> None:
    identity = uuid4()
    old = tmp_path / "historical.htm"
    old.write_text("immutable")
    for suffix in (".htm", ".png", "-holding.png"):
        (tmp_path / (identity.hex + suffix)).write_text("synthetic report")
    assert account_probe.remove_probe_reports(tmp_path, identity) == 3
    assert old.read_text() == "immutable"


@pytest.mark.parametrize("timeout", [False, True])
def test_one_native_launch_and_no_candidate_or_config_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timeout: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    pinned = binding(tmp_path)
    (pinned.terminal_data_root / "MQL5/Experts").mkdir(parents=True)
    context = assess(pinned, *records(tmp_path), 42)
    monkeypatch.setattr(account_probe, "discover", lambda _: context)
    monkeypatch.setattr(account_probe, "restrict_runtime", lambda _: None)
    monkeypatch.setattr(account_probe, "close_session", lambda *_: None)
    binary = tmp_path / "synthetic.ex5"
    binary.write_bytes(b"not executable")
    monkeypatch.setattr(
        account_probe,
        "compile_probe",
        lambda *_: {
            "status": "COMPILED",
            "ex5_path": str(binary),
            "ex5_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        },
    )

    class FakeObserver:
        def __init__(self, _: Path) -> None:
            self.processes: dict[int, dict[str, Any]] = {}

        def close(self) -> None:
            pass

    monkeypatch.setattr(account_probe, "Observer", FakeObserver)
    calls = []

    def native(*args: Any) -> Outcome:
        calls.append(args)
        assert args[0] == pinned.terminal_executable
        assert args[3] == 60.0
        ini = Path(args[1][0].removeprefix("/config:"))
        assert "Login=123456789" in ini.read_text()
        assert "Model=4" in ini.read_text() and "Optimization=0" in ini.read_text()
        assert len(list((pinned.terminal_data_root / "MQL5/Experts").iterdir())) == 1
        return Outcome(0, timed_out=timeout)

    monkeypatch.setattr(account_probe, "execute", native)
    saved = config(timeframe="M5")
    original = saved.model_dump_json()
    root = tmp_path / ".local/phase5_b1e/probe"
    result = account_probe.run_account_probe(pinned, root, saved)
    assert len(calls) == 1
    assert result["candidate_staged"] is False and result["baseline_result"] is False
    assert result["ephemeral_config_removed"] and result["probe_expert_removed"]
    assert result["status"] == (
        "BOOTSTRAP_TIMEOUT" if timeout else "PROCESS_EXITED_DURING_BOOTSTRAP"
    )
    assert not result["probe_init_succeeded"] and not result["first_tick_observed"]
    assert saved.model_dump_json() == original
    with pytest.raises(FileExistsError):
        account_probe.run_account_probe(pinned, root, saved)
    assert len(calls) == 1
