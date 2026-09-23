import pytest
from sqlalchemy import update

from tests.integration.test_monitoring import monitoring_migration as monitoring_migration
from tests.integration.test_mt5_bridge import bridge as bridge
from tests.mt5.fake import T
from trading_ecosystem.mt5.bridge import Bridge
from trading_ecosystem.mt5.calibration import retained_observations
from trading_ecosystem.mt5.cost_profile import profile_deals, profile_spreads
from trading_ecosystem.mt5.store import observations


def test_retained_sample_read_only_and_hash_verified(bridge: Bridge) -> None:
    assert bridge.step(T)
    before, identity = retained_observations(bridge.engine, bridge.scope)
    costs = profile_deals([r["body"] for r in before if r["kind"] == "DEAL"])
    spreads = profile_spreads(
        [(r["external_id"], r["body"]) for r in before if r["kind"] == "QUOTE"]
    )
    assert costs["deal_count"] == 1
    assert spreads["symbols"]
    assert retained_observations(bridge.engine, bridge.scope) == (before, identity)
    with bridge.engine.begin() as conn:
        conn.execute(
            update(observations)
            .where(observations.c.scope_id == bridge.scope.stream_id)
            .values(body={"tampered": True})
        )
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        retained_observations(bridge.engine, bridge.scope)
