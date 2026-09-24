from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest

from tests.features.fixtures import source
from tests.observer.fixtures import T, frame, position, session, trade
from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.features.builder import build_source
from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.features.dataset import validate_rows
from trading_ecosystem.observer.replay import replay


def test_preexisting_entry_and_partial_timing_unknown() -> None:
    frames = (
        frame(1, positions=(position(),)),
        frame(
            2,
            positions=({**position(), "volume": ".05"},),
            deals=(trade(1, 2, type=1, entry=1, volume=".05"),),
        ),
        frame(3, deals=(trade(2, 3, type=1, entry=1, volume=".05"),)),
    )
    events, episodes = replay(session(), frames)
    recorded = dict(
        session=session(),
        frames=frames,
        events=events,
        episodes=episodes,
        market={},
        manifest={"created_at": frames[-1].observed_at.isoformat()},
    )
    tables = build_source(recorded, BuildConfig())
    assert len(tables["episode_features"]) == 1 and not tables["entry_features"]
    row = tables["episode_features"][0]
    outcome = tables["episode_outcomes"][0]
    assert row["entry_time_known"] is False and row["entry_volume"] is None
    assert outcome["holding_duration"] is None and outcome["time_to_first_partial_close"] is None
    assert outcome["fraction_closed_first"] == "0.5"


def test_preexisting_scale_in_does_not_replace_original_unknown_entry() -> None:
    frames = (
        frame(1, positions=(position(),)),
        frame(
            2,
            positions=({**position(), "volume": ".05"},),
            deals=(trade(1, 2, type=1, entry=1, volume=".05"),),
        ),
        frame(3, positions=(position(),), deals=(trade(2, 3, volume=".05"),)),
        frame(4, deals=(trade(3, 4, type=1, entry=1),)),
    )
    events, episodes = replay(session(), frames)
    recorded = dict(
        session=session(),
        frames=frames,
        events=events,
        episodes=episodes,
        market={},
        manifest={"created_at": frames[-1].observed_at.isoformat()},
    )
    tables = build_source(recorded, BuildConfig())
    episode_row = tables["episode_features"][0]
    assert utc_timestamp(episode_row["prediction_cutoff"]) == frames[0].observed_at
    assert episode_row["entry_time_known"] is False and episode_row["entry_volume"] is None
    assert len(tables["entry_features"]) == 1
    assert tables["entry_features"][0]["entry_time_known"] is True


def test_nominal_equity_ratio_requires_matching_known_currency() -> None:
    recorded = source()
    frames = list(recorded["frames"])
    metadata = deepcopy(frames[1].metadata)
    metadata["BTCUSDm"]["currency_profit"] = "JPY"
    frames[1] = frames[1].model_copy(
        update={"metadata": metadata, "account": {"equity": "10000", "currency": "USD"}}
    )
    recorded["frames"] = tuple(frames)
    recorded["events"], recorded["episodes"] = replay(session(), tuple(frames))
    row = build_source(recorded, BuildConfig())["episode_features"][0]
    assert row["notional_to_equity"] is None
    assert row["quality"]["profit_currency"] == "JPY"


def test_scale_in_partial_close_and_first_observed_stop_behavior() -> None:
    recorded = source()
    frames = (
        frame(1),
        frame(2, positions=(position(),), deals=(trade(1, 2),)),
        frame(3, positions=({**position(), "volume": ".20", "sl": "96"},), deals=(trade(2, 3),)),
        frame(
            4,
            positions=({**position(), "volume": ".15", "sl": "96", "tp": None},),
            deals=(trade(3, 4, type=1, entry=1, volume=".05"),),
        ),
        frame(5, deals=(trade(4, 5, type=1, entry=1, volume=".15"),)),
    )
    recorded["frames"] = frames
    recorded["events"], recorded["episodes"] = replay(session(), frames)
    recorded["manifest"]["created_at"] = frames[-1].observed_at.isoformat()
    tables = build_source(recorded, BuildConfig())
    assert len(tables["entry_features"]) == 2 and len(tables["episode_features"]) == 1
    y = tables["episode_outcomes"][0]
    assert y["episode_entry_count"] == 2 and y["increase_count"] == 1
    assert y["max_volume_ratio"] == "1" and Decimal(y["median_entry_spacing_time"]) == 1
    assert (
        y["fraction_closed_first"] == "0.25" and y["fraction_closed_total_before_final"] == "0.25"
    )
    assert y["SL_change_count"] == 1 and y["TP_removed_count"] == 1
    assert y["SL_first_change_delay_observed"] == "1.0"


def test_prior_episode_sequence_uses_only_known_past_events() -> None:
    recorded = source()
    frames = (*recorded["frames"], frame(5, deals=(trade(3, 5, volume=".20"),)))
    recorded["frames"] = frames
    recorded["events"], recorded["episodes"] = replay(session(), frames)
    recorded["manifest"]["created_at"] = frames[-1].observed_at.isoformat()
    rows = build_source(recorded, BuildConfig())["episode_features"]
    later = next(r for r in rows if utc_timestamp(r["prediction_cutoff"]) == frames[-1].observed_at)
    assert later["previous_episode_direction"] == "BUY"
    assert later["volume_ratio_vs_previous"] == "2" and later["same_direction_sequence_length"] == 2
    assert later["time_since_previous_exit"] == "1.0"


def test_late_account_poll_is_not_promoted_to_broker_entry_state() -> None:
    recorded = source()
    frames = list(recorded["frames"])
    frames[1] = frames[1].model_copy(
        update={
            "observed_at": T + timedelta(seconds=2, microseconds=1),
            "account": {"equity": "999999", "balance": "999999"},
        }
    )
    recorded["frames"] = tuple(frames)
    recorded["events"], recorded["episodes"] = replay(session(), tuple(frames))
    row = build_source(recorded, BuildConfig())["episode_features"][0]
    assert row["entry_account_equity"] == "10000"  # Prior frame, not later discovery poll.
    assert row["initial_SL_distance"] is None


def test_unknown_attribution_does_not_create_known_sequence() -> None:
    recorded = source()
    for event in recorded["events"]:
        event["attribution"] = {"source": "UNKNOWN", "confidence": "UNKNOWN", "candidate_id": None}
    row = build_source(recorded, BuildConfig())["episode_features"][0]
    assert row["candidate_id"] is None and row["same_direction_sequence_length"] is None
    assert row["quality"]["ambiguous_attribution"]


@pytest.mark.parametrize("kind", ["duplicate", "bad_integer", "bad_boolean", "undocumented_null"])
def test_matrix_validation_is_fail_closed(kind: str) -> None:
    row = deepcopy(build_source(source(), BuildConfig())["episode_features"][0])
    rows = [row]
    if kind == "duplicate":
        rows.append(deepcopy(row))
    elif kind == "bad_integer":
        row["hour_utc"] = True
    elif kind == "bad_boolean":
        row["entry_time_known"] = 1
    else:
        row["h1_ema200"] = None
    with pytest.raises(ValueError):
        validate_rows(rows, causal=True)
