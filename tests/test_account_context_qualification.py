"""Offline presence is not authentication; runtime proof never grants campaign permission."""

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from tests.test_phase5b_environment import binding
from trading_ecosystem.tester import account_context_qualification as q


def fixture(tmp_path: Path) -> tuple[Any, dict[str, Any]]:
    pinned = binding(tmp_path).model_copy(update={"server": "Exness-MT5Trial14"})
    identity = uuid4()
    proof = {
        "terminal_binding": pinned.model_dump(mode="json"),
        "account_binding": {
            "account_binding_id": str(identity),
            "terminal_binding_id": str(pinned.terminal_binding_id),
            "environment_classification": "DEMO",
            "server": "Exness-MT5Trial14",
            "company": "Exness Technologies Ltd",
            "account_fingerprint": hashlib.sha256(identity.bytes + b"123456789").hexdigest(),
        },
    }
    return pinned, proof


def test_binding_orthogonal_deterministic_and_nonsecret(tmp_path: Path) -> None:
    pinned, proof = fixture(tmp_path)
    a = q.persisted_binding(pinned, proof)
    proof["account_binding"]["verified_at"] = "ignored observation time"
    b = q.persisted_binding(pinned, proof)
    assert a == b
    assert a["content"]["artifact_strategy"] == "PORTABLE_ARTIFACT"
    assert a["content"]["terminal_mode"] == "MAIN_MODE"
    assert a["content"]["state"] == "PERSISTED_ACCOUNT_CONTEXT_READY_FOR_RUNTIME_PROBE"
    assert "123456789" not in str(a)
    assert "password" not in str(a).lower()
    assert q.runtime_matches(123456789, a["content"])
    assert not q.runtime_matches(111111111, a["content"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("environment_classification", "REAL"),
        ("server", "wrong"),
        ("company", "wrong"),
        ("terminal_binding_id", str(uuid4())),
    ],
)
def test_wrong_attestation_rejected(tmp_path: Path, field: str, value: str) -> None:
    pinned, proof = fixture(tmp_path)
    proof["account_binding"][field] = value
    with pytest.raises(ValueError, match="BLOCKED_ACCOUNT_ATTESTATION_MISMATCH"):
        q.persisted_binding(pinned, proof)


def test_wrong_profile_rejected(tmp_path: Path) -> None:
    pinned, proof = fixture(tmp_path)
    proof["terminal_binding"]["terminal_data_root"] = str(tmp_path / "other")
    with pytest.raises(ValueError):
        q.persisted_binding(pinned, proof)


def test_running_terminal_blocks_without_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(q, "running_terminals", lambda: [{"ProcessId": 576}])
    with pytest.raises(ValueError, match="BLOCKED_PROFILE_IN_USE"):
        q.ownership_ready()


@pytest.mark.parametrize("present", [True, False])
def test_offline_store_metadata_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, present: bool
) -> None:
    pinned, proof = fixture(tmp_path)
    store = pinned.terminal_data_root / "config/accounts.dat"
    store.parent.mkdir(parents=True, exist_ok=True)
    if present:
        store.write_bytes(b"synthetic-store-never-opened")
    monkeypatch.setattr(q, "running_terminals", lambda: [])
    monkeypatch.setattr(q, "validate_binding", lambda *_: None)
    monkeypatch.setattr(q, "validate_artifact", lambda *_: None)
    monkeypatch.setattr(q, "file_identity", lambda *_: {"build": "6230"})
    monkeypatch.setattr(q, "environment_proof", lambda *_: proof)
    monkeypatch.setattr(q, "discover", lambda *_: pytest.fail("offline SDK access"))
    monkeypatch.setattr(Path, "read_bytes", lambda *_: pytest.fail("account store read"))
    if present:
        result = q.offline(pinned, tmp_path / "artifact")
        assert result["account_store_present"] and not result["runtime_authenticated"]
    else:
        with pytest.raises(ValueError, match="BLOCKED_ACCOUNT_STORE_ABSENT"):
            q.offline(pinned, tmp_path / "artifact")


@pytest.mark.parametrize("accepted", [True, False])
def test_success_requires_runtime_proof_and_never_authorizes(accepted: bool) -> None:
    lifecycle = {"tester_initialized": True, "cleanup_verified": True}
    records = [{"source": "Tester/agents/new.log", "message": "abc.ex5 loaded\nTest passed"}]
    runtime = {"state": "RUNTIME_ACCOUNT_CONTEXT_ACCEPTED" if accepted else "UNVERIFIED"}
    result = q.qualification_result(lifecycle, records, runtime, "abc")
    assert (result["environment"] == "READY") == accepted
    assert result["campaign_authorization"] == "NOT_AUTHORIZED"
    assert result["start_eligible"] is False
    assert result["campaign_budget_consumed"] == 0
    assert result["full_interval_real_tick_coverage"] == "UNKNOWN"
    assert "net_profit" not in result


@pytest.mark.parametrize("message", ["authorization failed", "", "generating based on real ticks"])
def test_generic_messages_never_prove_credential_requirement(message: str) -> None:
    result = q.qualification_result(
        {"tester_initialized": False, "cleanup_verified": True},
        [{"source": "Tester/new.log", "message": message}],
        {"state": "UNVERIFIED"},
        "abc",
    )
    assert result["status"] == "BOOTSTRAP_UNVERIFIED"


def test_dry_run_failure_never_launches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(q, "execute", lambda *_: pytest.fail("native launch"))
    with pytest.raises(ValueError, match="IGNORED_QUALIFICATION_ROOT_REQUIRED"):
        q.run(tmp_path / "probe", tmp_path / "artifact")


@pytest.mark.parametrize("same_source", [True, False])
def test_owned_tester_completed_exact_expert_supersedes_missing_banner(same_source: bool) -> None:
    result = q.qualification_result(
        {
            "tester_initialized": False,
            "cleanup_verified": True,
            "config_accepted": True,
            "stages": ["PROCESS_STARTED", "CONFIG_ACCEPTED", "TESTER_SUBSYSTEM_STARTING"],
        },
        [
            {"source": "Tester/new.log", "message": "expert abc.ex5 loaded"},
            {
                "source": "Tester/new.log" if same_source else "Tester/old.log",
                "message": "Test passed",
            },
        ],
        {"state": "RUNTIME_ACCOUNT_CONTEXT_ACCEPTED"},
        "abc",
    )
    assert (result["environment"] == "READY") == same_source
    assert not result["start_eligible"]
