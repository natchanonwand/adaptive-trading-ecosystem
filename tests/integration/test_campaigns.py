"""PostgreSQL software fixtures only; no REAL_DEMO_OBSERVATION export is produced."""

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from tests.campaigns.test_campaigns import specification
from tests.integration.test_external_observer import advance, fake
from tests.integration.test_external_observer import observer as observer
from tests.integration.test_monitoring import monitoring_migration as monitoring_migration
from tests.observer.fixtures import T, position, trade
from trading_ecosystem.campaigns.diagnostics import diagnostics
from trading_ecosystem.campaigns.finalize import finalize
from trading_ecosystem.campaigns.journal import Journal, create
from trading_ecosystem.campaigns.runtime import completed, db_size
from trading_ecosystem.features.builder import build_source, read_source
from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.observer.export import export_session
from trading_ecosystem.observer.runtime import Observer


def test_campaign_counts_recovered_episodes_without_duplicates(observer: Observer) -> None:
    client = fake(observer)
    assert advance(observer, 0)
    client.positions = (position(),)
    client.deals = (trade(1, 1),)
    assert advance(observer, 3)
    assert completed(observer, "fixture-a") == 0
    restarted = Observer(client, observer.engine, observer.session)
    client.positions = ()
    client.deals += (trade(2, 4, type=1, entry=1),)
    assert advance(restarted, 6)
    assert advance(restarted, 9)
    assert completed(restarted, "fixture-a") == 1
    assert completed(restarted, "another-candidate") == 0
    assert db_size(observer.engine) > 0


def test_synthetic_origin_cannot_finalize(observer: Observer, tmp_path: Path) -> None:
    root = tmp_path / "software-test-only"
    create(root, specification(fake(observer)))
    journal = Journal(root)
    journal.record("START", {"origin": "SYNTHETIC_QUALIFICATION"})
    journal.record("STOP", {"origin": "SYNTHETIC_QUALIFICATION", "status": "STOPPED_RECONCILED"})
    with pytest.raises(ValueError, match="NOT_ELIGIBLE"):
        finalize(root, observer.engine)
    assert not (root / "raw").exists()


def test_diagnostics_context_costs_and_censoring(observer: Observer, tmp_path: Path) -> None:
    client = fake(observer)
    observer = Observer(
        client,
        observer.engine,
        observer.session.model_copy(
            update={
                "session_id": uuid4(),
                "broker": client.account["company"],
                "server_scope": client.account["server"],
            }
        ),
    )
    spec = specification(client)
    # Use fixture identity for diagnostics only; never call real feature/finalization APIs.
    spec = spec.model_copy(
        update={
            "campaign_id": observer.session.session_id,
            "observer_config": observer.session.config,
            "metadata": spec.metadata.model_copy(
                update={
                    "candidate": observer.session.config.candidates[0],
                }
            ),
        }
    )
    client.positions = (position(),)
    client.deals = (trade(1, 0),)
    assert advance(observer, 0)
    client.positions = ()
    client.deals += (trade(2, 3, entry=1, type=1, reason=5),)
    assert advance(observer, 3)
    with observer.engine.connect() as conn:
        export_session(conn, observer.session, tmp_path / "raw")
    source = read_source(tmp_path / "raw", raw_replay=True)
    entries = build_source(source, BuildConfig())["entry_features"]
    stop = dict(
        started_at=T.isoformat(), ended_at=(T + timedelta(seconds=3)).isoformat(), wall_seconds=3
    )
    result = diagnostics(spec, source, entries, stop)
    assert set(result["market_context_coverage"]) == {"M1", "M5", "M15", "M30", "H1", "H4"}
    assert result["observed_costs"]["commission"]["observed_deals"] == 2
    assert result["observed_costs"]["commission"]["observed_sum"] == "-0.02"
    assert result["broker_exit_reason_codes"] == {"5": 1}
    assert result["during_observation_entry_events"] == 1
    assert result["historical_recovered_entry_events"] == 0
    assert result["market_context_coverage"]["M1"]["entries"] == 1
    wrong = spec.model_copy(update={"terminal_build": 999})
    with pytest.raises(ValueError, match="IDENTITY"):
        diagnostics(wrong, source, entries, stop)
    mixed = {
        **source,
        "episodes": [
            {**e, "attribution": {"source": "UNKNOWN", "confidence": "AMBIGUOUS"}}
            for e in source["episodes"]
        ],
    }
    with pytest.raises(ValueError, match="MIXED_ATTRIBUTION"):
        diagnostics(spec, mixed, entries, stop)
