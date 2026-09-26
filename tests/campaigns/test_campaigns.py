"""Software-only campaign checks. These fixtures never qualify as real observations."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from tests.observer.fixtures import FakeObserver, T
from trading_ecosystem.behavioral_research.contracts import ResearchConfig
from trading_ecosystem.campaigns.__main__ import evidence_path
from trading_ecosystem.campaigns.contracts import EaMetadata, RealEaQualificationCampaign
from trading_ecosystem.campaigns.finalize import ready
from trading_ecosystem.campaigns.health import account_guard, audit_read_only, inspect_health
from trading_ecosystem.campaigns.journal import Journal, append, create, read, status, write_new
from trading_ecosystem.campaigns.runtime import run
from trading_ecosystem.observer.contracts import Candidate, Config


def specification(fake: FakeObserver | None = None) -> RealEaQualificationCampaign:
    fake = fake or FakeObserver()
    session = fake.observation_session()
    candidate = Candidate(
        ea_id="software-test-only",
        display_name="Not a real campaign",
        vendor="Test vendor",
        magic_numbers=(77,),
        symbols=("BTCUSDm",),
        exclusive_binding=True,
        attribution_reference="unit-test-attestation-not-real-evidence",
    )
    return RealEaQualificationCampaign(
        campaign_id=uuid4(),
        account_scope=session.account_scope,
        broker=fake.account["company"],
        server=fake.account["server"],
        terminal_build=session.terminal_build,
        metadata=EaMetadata(
            candidate=candidate,
            license_status="VENDOR_DEMO",
            license_attestation_reference="TEST_ONLY",
            charts=("BTCUSDm/M5",),
            user_confirms_attached=True,
            attribution_valid_from=T - timedelta(days=2),
            settings_hash="0" * 64,
            settings_local_reference="TEST_ONLY",
        ),
        window_start=T,
        window_end=T + timedelta(seconds=30),
        bridge_stream_id=uuid4(),
        observer_config=Config(symbols=candidate.symbols, candidates=(candidate,)),
        research_config=ResearchConfig(candidate_id=candidate.ea_id),
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("license_status", "UNATTESTED"),
        ("license_attestation_reference", None),
        ("user_confirms_attached", False),
        ("charts", ()),
        ("attribution_valid_from", None),
    ],
)
def test_missing_attestation_blocks(field: str, value: Any) -> None:
    assert not specification().metadata.model_copy(update={field: value}).ready()


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", "MANUAL"),
        ("exclusive_binding", False),
        ("vendor", None),
        ("attribution_reference", None),
        ("magic_numbers", (0,)),
        ("status", "DISABLED"),
        ("ea_id", "fixture-a"),
    ],
)
def test_candidate_not_accepted_by_magic_alone(field: str, value: Any) -> None:
    m = specification().metadata
    assert not m.model_copy(
        update={"candidate": m.candidate.model_copy(update={field: value})}
    ).ready()


@pytest.mark.parametrize(
    "field,value",
    [
        ("window_end", T),
        ("window_end", T + timedelta(days=2)),
        ("environment", "REAL"),
        ("feature_set_id", "changed"),
        ("research_engine_version", "changed"),
        ("research_config", {}),
    ],
)
def test_invalid_identity_rejected(field: str, value: Any) -> None:
    body = specification().model_dump()
    body[field] = value
    with pytest.raises(ValueError):
        RealEaQualificationCampaign.model_validate(body)


def test_binding_must_cover_history() -> None:
    body = specification().model_dump()
    body["metadata"]["attribution_valid_from"] = T
    with pytest.raises(ValueError, match="LOOKBACK"):
        RealEaQualificationCampaign.model_validate(body)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("trade_mode", 2, "NOT_DEMO"),
        ("trade_mode", False, "NOT_DEMO"),
        ("login", -1, "ACCOUNT_SWITCH"),
        ("server", "other", "ACCOUNT_SWITCH"),
    ],
)
def test_account_switch_fails_closed(field: str, value: Any, reason: str) -> None:
    client = FakeObserver()
    spec = specification(client)
    client.account[field] = value
    with pytest.raises(ValueError, match=reason):
        account_guard(spec, client)


def test_guard_and_static_audit() -> None:
    client = FakeObserver()
    client.terminal["trade_allowed"] = True
    assert account_guard(specification(client), client)["environment"] == "DEMO"
    assert audit_read_only()


def test_health_uses_actual_observer_api_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def get(port: int, path: str) -> tuple[int, bytes]:
        if path == "/health":
            return 200, b'{"status":"HEALTHY","database":"HEALTHY","read_only":true}'
        if path == "/api/v1/observer":
            return 200, b'{"sessions":[],"selected":null,"has_more_sessions":false}'
        return 200, b'<div id="root"></div>'

    monkeypatch.setattr("trading_ecosystem.campaigns.health.local_get", get)
    engine = create_engine("sqlite://")
    try:
        result = inspect_health(specification(), FakeObserver(), engine, T)
        assert result["checks"]["observer"] and result["checks"]["dashboard"]
        assert not result["passed"] and not result["checks"]["bridge"]
    finally:
        engine.dispose()


@pytest.mark.parametrize("mutation", ["body", "sequence", "previous_hash", "spec", "missing"])
def test_journal_corruption_rejected(tmp_path: Path, mutation: str) -> None:
    root = tmp_path / "journal-test"
    create(root, specification())
    journal = Journal(root)
    journal.record("START", {"at": T.isoformat()})
    journal.record("STOP", {"status": "PAUSED"})
    assert len(read(root)) == 2
    path = root / "journal/00000002.json"
    row = json.loads(path.read_bytes())
    if mutation == "missing":
        (root / "journal/00000001.json").unlink()
    elif mutation == "spec":
        path = root / "campaign.json"
        row = json.loads(path.read_bytes())
        row["terminal_build"] += 1
        path.write_text(json.dumps(row))
    else:
        row[mutation] = "tampered"
        path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="INTEGRITY"):
        read(root)


def test_no_overwrite_or_automatic_resume(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    create(root, specification())
    append(root, "START", {"origin": "SOFTWARE_TEST_ONLY"})
    assert not status(root)["automatic_resume"]
    with pytest.raises(FileExistsError):
        create(root, specification())
    with pytest.raises(ValueError):
        ready(root)
    write_new(root / "manifest.json", {})
    with pytest.raises(ValueError, match="IMMUTABLE"):
        append(root, "STOP", {})


def test_fake_client_cannot_start_real_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "trading_ecosystem.campaigns.runtime.inspect_health", lambda *a: {"passed": True}
    )
    engine = create_engine("sqlite://")
    root = tmp_path / "never-created"
    try:
        with pytest.raises(ValueError, match="NATIVE_READ_CLIENT"):
            run(specification(), FakeObserver(), engine, root)
        assert not root.exists()
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "path", ["data/datasets/new", ".local/phase4_d/new", ".local/phase4_e/campaigns"]
)
def test_output_namespace(path: str) -> None:
    with pytest.raises(ValueError, match="NAMESPACE"):
        evidence_path(Path(path))
