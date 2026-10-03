"""Non-executing plan validation and proof integrity; synthetic files only."""

import configparser
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from tests.phase5b_helpers import config
from tests.test_phase5b_environment import binding
from trading_ecosystem.tester.qualification import (
    digest,
    environment_proof,
    ingestion,
    render,
    verify_binding,
)


def proof(root: Path, terminal: object) -> Path:
    from trading_ecosystem.tester.environment import TerminalBinding

    assert isinstance(terminal, TerminalBinding)
    root.mkdir()
    account = {
        "account_binding_id": str(uuid4()),
        "terminal_binding_id": str(terminal.terminal_binding_id),
        "environment_classification": "DEMO",
        "server": terminal.server,
    }
    result = {
        "schema": "PHASE5B1E_ACCOUNT_PROBE_V1",
        "status": "BOOTSTRAP_READY",
        "probe_init_succeeded": True,
        "first_tick_observed": True,
        "cleanup_verified": True,
        "account_binding": account,
        "candidate_staged": False,
        "baseline_result": False,
        "terminal_binding_id": str(terminal.terminal_binding_id),
        "terminal_sha256": terminal.terminal_sha256,
        "terminal_build": terminal.terminal_build,
        "probe_id": str(uuid4()),
    }
    for name, value in [("assessment.json", result), ("account-binding.json", account)]:
        (root / name).write_text(json.dumps(value))
    remanifest(root)
    return root


def remanifest(root: Path) -> None:
    (root / "files.json").write_text(
        json.dumps(
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.glob("*.json")
                if p.name != "files.json"
            }
        )
    )


@pytest.mark.parametrize(
    "source,expected",
    [
        ("USER_SUPPLIED_AUTHORIZED", "USER_SUPPLIED_EX5"),
        ("MARKETPLACE_AUTHORIZED", "AUTHORIZED_MT5_INSTALLED_EA"),
    ],
)
def test_supported_provenance_modes(source: str, expected: str) -> None:
    assert ingestion(source) == expected


@pytest.mark.parametrize("source", ["UNKNOWN", "FREE_VENDOR_DISTRIBUTION", "filename.ex5"])
def test_unknown_ingestion_not_invented(source: str) -> None:
    with pytest.raises(ValueError, match="BLOCKED_CANDIDATE_INGESTION_MODEL"):
        ingestion(source)


def test_native_dry_run_exact_fields() -> None:
    cfg = config(
        timeframe="M5", from_date="2026-01-01", to_date="2026-06-30", initial_deposit="300"
    )
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(render(cfg, "Market\\Synthetic EA.ex5", "Synthetic-Demo"))
    assert dict(parser["Tester"]) == {
        "expert": "Market\\Synthetic EA.ex5",
        "symbol": "XAUUSDm",
        "period": "M5",
        "model": "4",
        "optimization": "0",
        "forwardmode": "0",
        "uselocal": "1",
        "useremote": "0",
        "usecloud": "0",
        "visual": "0",
        "fromdate": "2026.01.01",
        "todate": "2026.06.30",
        "deposit": "300",
        "currency": "USD",
        "leverage": "1:100",
        "report": cfg.baseline_run_id.hex + ".htm",
        "replacereport": "0",
        "shutdownterminal": "1",
    }
    assert parser["Experts"]["enabled"] == "0" and parser["Experts"]["allowlivetrading"] == "0"
    assert "login" not in parser["Common"] and "password" not in parser["Common"]


@pytest.mark.parametrize("expert", ["..\\a.ex5", "C:\\a.ex5", "a.ex5\nLogin=1", "a/../b.ex5"])
def test_unsafe_expert_reference_rejected(expert: str) -> None:
    with pytest.raises(ValueError):
        render(config(), expert, "Synthetic-Demo")


@pytest.mark.parametrize("case", ["valid", "tamper", "terminal", "live"])
def test_environment_proof(tmp_path: Path, case: str) -> None:
    terminal = binding(tmp_path)
    root = proof(tmp_path / "proof", terminal)
    if case == "tamper":
        (root / "assessment.json").write_text("{}")
    if case == "terminal":
        terminal = terminal.model_copy(update={"terminal_binding_id": uuid4()})
    if case == "live":
        value = json.loads((root / "account-binding.json").read_text())
        value["environment_classification"] = "LIVE"
        (root / "account-binding.json").write_text(json.dumps(value))
        remanifest(root)
    if case == "valid":
        value = environment_proof(terminal, root)
        assert value["status"] == "BOOTSTRAP_READY_AS_OBSERVED"
        assert value["revalidate_at_execution"] and value["full_interval_real_ticks"] == "UNKNOWN"
    else:
        with pytest.raises(ValueError, match="BLOCKED_"):
            environment_proof(terminal, root)


def test_binding_rejects_substitution() -> None:
    body = {"candidate": "one", "config": "one", "account": "one"}
    record = {"content": body, "identity": digest(body)}
    verify_binding(record, record)
    for key in body:
        changed = {**body, key: "other"}
        with pytest.raises(ValueError, match="BINDING_CHANGED"):
            verify_binding(record, {"content": changed, "identity": digest(changed)})
