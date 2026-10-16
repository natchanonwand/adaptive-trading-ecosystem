from pathlib import Path

import pytest

from trading_ecosystem.tester.transport import assess_transport, sandbox_path


def body(root: Path) -> bytes:
    # Public diagnostic protocol labels, not encoded credentials.
    return (
        "STARTED\nschema=RUNTIME_TRANSPORT_V1\n"  # pragma: allowlist secret
        "script=RuntimeTransportProbe\n"  # pragma: allowlist secret
        f"version=1.00\nbuild=6230\ndata_path={root}\nCOMPLETED\n"
    ).encode()


def assess(raw: bytes | None, root: Path, **changes: bool) -> dict[str, object]:
    options = dict(terminal_started=True, dispatched=True, script_returned=True, normal_exit=True)
    options.update(changes)
    return assess_transport(raw, root, **options)


def test_success_and_identity(tmp_path: Path) -> None:
    result = assess(body(tmp_path), tmp_path)
    assert result["status"] == "RUNTIME_ATTESTATION_TRANSPORT_READY"
    assert result["payload_identity"] == assess(body(tmp_path), tmp_path)["payload_identity"]
    assert result["profile_isolation"] == "NOT_ASSESSED"
    assert result["readback_verified"]


def test_expected_sandbox(tmp_path: Path) -> None:
    assert sandbox_path(tmp_path) == tmp_path / "MQL5/Files/RuntimeTransportProbe.txt"


@pytest.mark.parametrize(
    "raw,changes,status",
    [
        (None, {"dispatched": False}, "BLOCKED_STARTUP_SCRIPT_DISPATCH"),
        (None, {}, "UNKNOWN_TRANSPORT_FAILURE"),
        (b"STARTED\n", {}, "BLOCKED_SCRIPT_RUNTIME"),
        (b"COMPLETED\n", {}, "BLOCKED_EVIDENCE_READBACK"),
        (None, {"write_failed": True}, "BLOCKED_EVIDENCE_FILE_WRITE"),
        (None, {"runtime_failed": True}, "BLOCKED_SCRIPT_RUNTIME"),
    ],
)
def test_failure_semantics(
    tmp_path: Path, raw: bytes | None, changes: dict[str, bool], status: str
) -> None:
    assert assess(raw, tmp_path, **changes)["status"] == status


def test_completion_does_not_prove_shutdown(tmp_path: Path) -> None:
    result = assess(body(tmp_path), tmp_path, normal_exit=False)
    assert result["complete_marker"] and result["script_returned"]
    assert result["status"] == "BLOCKED_SCRIPT_DRIVEN_SHUTDOWN"


def test_loaded_script_is_not_proof_of_onstart(tmp_path: Path) -> None:
    result = assess(None, tmp_path)
    assert result["startup_script_load_observed"]
    assert not result["onstart_verified"]
    assert result["status"] == "UNKNOWN_TRANSPORT_FAILURE"


def test_completion_does_not_prove_return(tmp_path: Path) -> None:
    assert assess(body(tmp_path), tmp_path, script_returned=False)["status"] == (
        "BLOCKED_SCRIPT_RUNTIME"
    )


@pytest.mark.parametrize("extra", [b"password=secret\n", b"timestamp=volatile\n", b"build=6230\n"])
def test_unexpected_or_duplicate_fields_rejected(tmp_path: Path, extra: bytes) -> None:
    raw = body(tmp_path).replace(b"COMPLETED", extra + b"COMPLETED")
    result = assess(raw, tmp_path)
    assert result["status"] == "BLOCKED_EVIDENCE_READBACK"
    assert result["payload"] is None


def test_wrong_root_and_build(tmp_path: Path) -> None:
    assert not assess(body(tmp_path), tmp_path / "other")["readback_verified"]
    assert not assess(body(tmp_path).replace(b"6230", b"6231"), tmp_path)["readback_verified"]


def test_no_research_side_effects(tmp_path: Path) -> None:
    before = list(tmp_path.iterdir())
    result = assess(body(tmp_path), tmp_path)
    assert list(tmp_path.iterdir()) == before
    assert not {"ExperimentRun", "ResearchWorkspaceIdentity", "budget"}.intersection(result)


def test_probe_has_no_account_or_chart_or_wait_calls() -> None:
    source = Path("src/trading_ecosystem/tester/RuntimeTransportProbe.mq5").read_text()
    for forbidden in [
        "AccountInfo",
        "Chart",
        "OrderSend",
        "CTrade",
        "Sleep(",
        "while(",
        "for(",
        "EventSetTimer",
        "WebRequest",
        "#import",
        "GlobalVariable",
    ]:
        assert forbidden not in source
    assert source.index('"STARTED\\n"') < source.index('"COMPLETED\\n"')


def test_tester_blocks_even_valid_payload(tmp_path: Path) -> None:
    assert assess(body(tmp_path), tmp_path, tester_observed=True)["status"] == (
        "BLOCKED_UNEXPECTED_TESTER_PROCESS"
    )
