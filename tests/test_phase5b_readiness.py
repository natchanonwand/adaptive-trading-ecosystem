"""Readiness model and immutable checkpoint contracts."""

import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from tests.phase5b_helpers import config
from trading_ecosystem.tester.checkpoint import verify_checkpoint
from trading_ecosystem.tester.readiness import Authorization, BaselineConfiguration


def specification(**changes: object) -> BaselineConfiguration:
    params = config().model_dump(exclude={"baseline_run_id", "project_id", "configuration_id"})
    params.update(changes)
    return BaselineConfiguration(
        configuration_id=uuid4(), project_id=uuid4(), parameters=params, confirmed=True
    )


@pytest.mark.parametrize(
    "change",
    [
        {"from_date": "2026-09-03", "to_date": "2026-09-02"},
        {"initial_deposit": "0"},
        {"leverage": 0},
        {"leverage": 2001},
        {"timeframe": "M2"},
        {"symbol": "XAUUSD"},
        {"tester_model": "OPEN_PRICES"},
        {"environment": "LIVE"},
        {"input_provenance": "USER_SUPPLIED_SET"},
        {"input_provenance": "VENDOR_DOCUMENTED_DEFAULTS"},
        {"baseline_run_id": str(uuid4())},
    ],
)
def test_invalid_specifications(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        specification(**change)


@pytest.mark.parametrize("provenance", ["USER_SUPPLIED_SET", "USER_CONFIRMED_VALUES"])
def test_exact_input_provenance(provenance: str) -> None:
    spec = specification(input_provenance=provenance, set_text="Lots=0.01")
    assert spec.execution(uuid4()).set_text == "Lots=0.01"


def test_authorization_requires_support_and_no_credentials() -> None:
    values = dict(
        event_id=uuid4(),
        provenance="FREE_VENDOR_DISTRIBUTION",
        source_reference="UNKNOWN",
        source_label="Vendor",
        authorization_basis="Explicit permission",
        confirmed=True,
    )
    with pytest.raises(ValueError):
        Authorization.model_validate(values)
    values["source_reference"] = "password=not-a-real-secret"
    with pytest.raises(ValueError):
        Authorization.model_validate(values)


def test_checkpoint_descendants_and_moved_lineage(tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init")
    git("config", "user.name", "Synthetic test")
    git("config", "user.email", "synthetic@example.invalid")
    git("commit", "--allow-empty", "-m", "first")
    first = git("rev-parse", "HEAD")
    git("tag", "old")
    git("commit", "--allow-empty", "-m", "checkpoint")
    checkpoint = git("rev-parse", "HEAD")
    git("tag", "current")
    git("update-ref", "refs/remotes/origin/main", checkpoint)
    lineage = (("old", first), ("current", checkpoint))
    assert verify_checkpoint(tmp_path, "current", lineage) == checkpoint
    with pytest.raises(ValueError, match="WRONG_IMMEDIATE"):
        verify_checkpoint(tmp_path, "old", lineage)
    git("commit", "--allow-empty", "-m", "work")
    assert verify_checkpoint(tmp_path, "current", lineage) == checkpoint
    git("tag", "-f", "old", checkpoint)
    with pytest.raises(ValueError, match="FROZEN_TAG_CHANGED"):
        verify_checkpoint(tmp_path, "current", lineage)
    git("tag", "-f", "old", first)
    git("tag", "-f", "current", "HEAD")
    with pytest.raises(ValueError, match="FROZEN_TAG_CHANGED"):
        verify_checkpoint(tmp_path, "current", lineage)
