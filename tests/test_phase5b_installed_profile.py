"""Synthetic in-place adapter boundaries; no native launch or real broker material."""

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from tests.test_phase5b_environment import binding
from tests.test_phase5b_qualification import proof, remanifest
from trading_ecosystem.tester.environment import TerminalBinding
from trading_ecosystem.tester.installed_profile import (
    InstalledProfileAdapter,
    installed_path,
    public_summary,
    strategy,
)
from trading_ecosystem.tester.qualification import environment_proof


def complete_proof(root: Path, terminal: TerminalBinding) -> Path:
    root = proof(root, terminal)
    account = json.loads((root / "account-binding.json").read_bytes())
    account.update(
        company="Synthetic demo company",
        account_fingerprint="a" * 64,
        verified_at="2026-10-02T00:00:00Z",
        discovery_source="PINNED_RUNNING_SESSION",
    )
    result = json.loads((root / "assessment.json").read_bytes())
    result.update(
        account_binding=account,
        observations=[
            {
                "component": "Terminal",
                "source": "logs/synthetic",
                "message": str(terminal.terminal_data_root),
            }
        ],
        processes=[
            {
                "role": "terminal",
                "identity_verified": True,
                "image": str(terminal.terminal_executable),
                "sha256": terminal.terminal_sha256,
            }
        ],
    )
    (root / "account-binding.json").write_text(json.dumps(account))
    (root / "assessment.json").write_text(json.dumps(result))
    remanifest(root)
    return root


def proposal(root: Path) -> tuple[dict[str, Any], TerminalBinding, Path]:
    terminal = binding(root)
    evidence = complete_proof(root / "proof", terminal)
    installed = terminal.terminal_data_root / "MQL5/Experts/Market/Synthetic EA.ex5"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"synthetic candidate")
    sha = hashlib.sha256(installed.read_bytes()).hexdigest()
    candidate_id, artifact_id = str(uuid4()), str(uuid4())
    return (
        {
            "ingestion_mode": "AUTHORIZED_MT5_INSTALLED_EA",
            "environment": environment_proof(terminal, evidence),
            "authorization": {
                "candidate_id": candidate_id,
                "provenance": "MARKETPLACE_AUTHORIZED",
                "confirmed": True,
            },
            "artifact": {
                "artifact_id": artifact_id,
                "role": "EA",
                "filename": installed.name,
                "sha256": sha,
                "size": installed.stat().st_size,
            },
            "candidate": {
                "candidate_id": candidate_id,
                "artifact_id": artifact_id,
                "artifact_sha256": sha,
                "product_name": "Synthetic EA",
            },
            "project": {"candidate_id": candidate_id},
            "expert_reference": "Market\\Synthetic EA.ex5",
            "expert_path": str(installed),
            "baseline_configuration": {
                "specification": {
                    "parameters": {"set_text": None, "input_provenance": "TESTER_DEFAULTS"}
                }
            },
        },
        terminal,
        evidence,
    )


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "hash",
        "same_name",
        "profile",
        "terminal",
        "account",
        "live",
        "build",
        "preset",
        "candidate",
        "authorization",
        "proof_tamper",
    ],
)
def test_in_place_identity_and_coherence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    data, terminal, evidence = proposal(tmp_path)
    installed = Path(data["expert_path"])
    if case in {"hash", "same_name"}:
        installed.write_bytes(b"wrong candidate")
    if case == "profile":
        assessment = json.loads((evidence / "assessment.json").read_bytes())
        assessment["observations"][0]["message"] = str(tmp_path / "other")
        (evidence / "assessment.json").write_text(json.dumps(assessment))
        remanifest(evidence)
        data["environment"] = environment_proof(terminal, evidence)
    if case == "terminal":
        terminal = terminal.model_copy(update={"terminal_binding_id": uuid4()})
    if case == "account":
        data["environment"]["account_binding"]["terminal_binding_id"] = str(uuid4())
    if case == "live":
        data["environment"]["account_binding"]["environment_classification"] = "LIVE"
    if case == "build":
        terminal = terminal.model_copy(update={"terminal_build": "9999"})
    if case == "preset":
        presets = terminal.terminal_data_root / "MQL5/Profiles/Tester"
        presets.mkdir(parents=True)
        (presets / "Synthetic EA.set").write_text("changed inputs")
    if case == "candidate":
        data["project"]["candidate_id"] = str(uuid4())
    if case == "authorization":
        data["authorization"]["confirmed"] = False
    if case == "proof_tamper":
        (evidence / "assessment.json").write_text("{}")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("No copy, launch, SDK, or license-storage reads")

    import shutil

    from trading_ecosystem.tester import process, research_account

    monkeypatch.setattr(shutil, "copyfile", forbidden)
    monkeypatch.setattr(process, "execute", forbidden)
    monkeypatch.setattr(research_account, "discover", forbidden)
    original = Path.read_bytes
    allowed = {installed, evidence / "assessment.json"}

    def guarded(path: Path) -> bytes:
        assert path in allowed, "Unexpected file read, including license/account storage"
        return original(path)

    with monkeypatch.context() as m:
        m.setattr(Path, "read_bytes", guarded)
        if case == "valid":
            plan = InstalledProfileAdapter().dry_run(data, terminal, evidence)
            assert plan["installed_sha256"] == data["artifact"]["sha256"]
            assert plan["execution_strategy"] == "INSTALLED_PROFILE_REFERENCE"
            assert not plan["binary_copy"] and not plan["native_launch_enabled"]
        else:
            with pytest.raises(ValueError):
                InstalledProfileAdapter().dry_run(data, terminal, evidence)
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "name",
    [
        "..\\escape.ex5",
        "../escape.ex5",
        "C:\\other.ex5",
        "/other.ex5",
        "\\\\server\\ea.ex5",
        "Market\\ea.ex5",
        "ea.ex5:stream",
        "ea.ex5\nLogin=1",
        "ea.dll",
        "NUL.ex5",
    ],
)
def test_untrusted_reference_rejected(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError):
        installed_path(binding(tmp_path), name)


@pytest.mark.parametrize("kind", ["is_symlink", "is_junction"])
def test_linked_parent_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    data, terminal, _ = proposal(tmp_path)
    target = Path(data["expert_path"]).parent
    monkeypatch.setattr(Path, kind, lambda p: p == target, raising=False)
    with pytest.raises(ValueError):
        installed_path(terminal, "Synthetic EA.ex5")


def test_portable_strategy_and_summary_privacy() -> None:
    assert strategy("USER_SUPPLIED_EX5") == "PORTABLE_ARTIFACT"
    assert strategy("AUTHORIZED_MT5_INSTALLED_EA") == "INSTALLED_PROFILE_REFERENCE"
    with pytest.raises(ValueError):
        strategy("untrusted")
    summary = public_summary(
        {
            "configuration_id": "synthetic",
            "status": "BLOCKED_CANDIDATE_PROFILE_MISMATCH",
            "authorization": "VERIFIED",
            "artifact": "VERIFIED",
            "native_config_dry_run": "NOT_RENDERED",
            "declared_license_status": "UNKNOWN",
            "declared_tester_access_status": "UNKNOWN",
            "observed_tester_access_status": "UNKNOWN",
            "expert_path": "PRIVATE_PATH",
        }
    )
    assert "PRIVATE_PATH" not in json.dumps(summary)
    assert summary["license"] == summary["tester_access"] == "UNKNOWN"
    assert not summary["execution_available"]
