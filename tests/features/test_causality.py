from copy import deepcopy
from datetime import timedelta

import pytest

from tests.features.fixtures import source
from tests.observer.fixtures import T
from trading_ecosystem.features.builder import build_source
from trading_ecosystem.features.contracts import BuildConfig, SessionWindow
from trading_ecosystem.features.dataset import validate_rows
from trading_ecosystem.features.families import closed_bars
from trading_ecosystem.features.registry import CATALOG
from trading_ecosystem.features.temporal import temporal
from trading_ecosystem.observer.context import TIMEFRAMES
from trading_ecosystem.observer.replay import replay


def test_full_source_features_and_separate_outcomes() -> None:
    tables = build_source(source(), BuildConfig())
    x, y = tables["episode_features"][0], tables["episode_outcomes"][0]
    validate_rows([x], causal=True)
    validate_rows([y], causal=False)
    assert x["h1_ema200"] == "100" and x["m15_atr14"] == "2"
    assert x["initial_SL_distance"] == "5" and x["reward_to_risk_observed"] == "2"
    assert y["gross_observed_pnl"] == "10"
    assert "gross_observed_pnl" not in x and "holding_duration" not in x
    assert len(CATALOG) == 100 and len({d.name for d in CATALOG}) == 100


@pytest.mark.parametrize("kind", ["future_candle", "exit", "later_SL", "later_account"])
def test_adversarial_future_information_cannot_change_x(kind: str) -> None:
    original = source()
    changed = deepcopy(original)
    if kind == "future_candle":
        for window in changed["market"].values():
            if "bars" in window:
                window["bars"].append(
                    dict(
                        time=int(T.timestamp()) + 10000,
                        open="999999",
                        high="999999",
                        low="999999",
                        close="999999",
                    )
                )
    else:
        frames = list(changed["frames"])
        if kind == "exit":
            frames[-1] = frames[-1].model_copy(
                update={"deals": ({**frames[-1].deals[0], "profit": "999999", "price": "999999"},)}
            )
        elif kind == "later_SL":
            frames[2] = frames[2].model_copy(
                update={"positions": ({**frames[2].positions[0], "sl": "999999"},)}
            )
        else:
            frames[2] = frames[2].model_copy(
                update={"account": {"equity": "999999", "balance": "999999"}}
            )
        changed["frames"] = tuple(frames)
        changed["events"], changed["episodes"] = replay(changed["session"], tuple(frames))
    before = build_source(original, BuildConfig())["episode_features"]
    after = build_source(changed, BuildConfig())["episode_features"]
    assert before == after


@pytest.mark.parametrize("tf", list(TIMEFRAMES))
def test_bar_close_exact_and_one_second_after_cutoff(tf: str) -> None:
    seconds = TIMEFRAMES[tf][1]
    bar = dict(time=int(T.timestamp()), open="100", high="101", low="99", close="100")
    window = dict(timeframe=tf, duration_seconds=seconds, bars=[bar])
    assert closed_bars(window, T + timedelta(seconds=seconds - 1), tf) == []
    assert closed_bars(window, T + timedelta(seconds=seconds), tf) == [bar]


def test_incomplete_m15_at_103715_and_utc_windows() -> None:
    at = T.replace(hour=10, minute=37, second=15)
    bars = [
        dict(
            time=int(T.replace(hour=10, minute=m).timestamp()),
            open="1",
            high="2",
            low="1",
            close="1",
        )
        for m in (15, 30)
    ]
    assert (
        closed_bars(dict(timeframe="M15", duration_seconds=900, bars=bars), at, "M15") == bars[:1]
    )
    assert temporal(T, BuildConfig())["session"] == "UTC_00_08"
    config = BuildConfig(
        session_windows=(SessionWindow(name="CROSS_UTC", start_minute_utc=1380, end_minute_utc=60),)
    )
    assert temporal(T, config)["minutes_since_session_open"] == 60


def test_missing_timeframe_and_insufficient_history_are_null() -> None:
    changed = source()
    for value in changed["market"].values():
        if "bars" in value:
            value["bars"] = value["bars"][-10:]
    row = build_source(changed, BuildConfig())["episode_features"][0]
    assert row["h1_ema200"] is None and row["m15_atr14"] is None
    assert row["quality"]["missing"]["h1_ema200"] == "INSUFFICIENT_HISTORY"


def test_firewall_rejects_future_availability_outcome_injection_and_nonfinite() -> None:
    row = build_source(source(), BuildConfig())["episode_features"][0]
    for mutation in ("future", "outcome", "nonfinite"):
        changed = deepcopy(row)
        if mutation == "future":
            changed["availability"]["h1_ema200"] = (T + timedelta(days=1)).isoformat()
        elif mutation == "outcome":
            changed["net_observed_pnl"] = "10"
        else:
            changed["h1_ema200"] = "Infinity"
        with pytest.raises(ValueError):
            validate_rows([changed], causal=True)


def test_fake_cannot_be_relabelled_real() -> None:
    with pytest.raises(ValueError, match="SYNTHETIC"):
        build_source(source(), BuildConfig(dataset_type="REAL_DEMO_OBSERVATION"))
