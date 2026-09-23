import ast
from datetime import timedelta
from pathlib import Path

import pytest

from tests.observer.fixtures import T, config, frame, position, session, trade
from trading_ecosystem.mt5.calculations import CALCULATION_METHODS, READ_METHODS
from trading_ecosystem.observer.context import TIMEFRAMES, build_context
from trading_ecosystem.observer.contracts import Candidate, Config, attribute
from trading_ecosystem.observer.replay import replay
from trading_ecosystem.observer.summary import summarize


@pytest.mark.parametrize("magic", [77, 78])
def test_explicit_binding_multiple_magic(magic: int) -> None:
    result = attribute({"magic": magic, "symbol": "BTCUSDm"}, config())
    assert result.confidence == "KNOWN" and result.source == "EXTERNAL_EA"


def test_duplicate_magic_ambiguous_and_magic_alone_not_identity() -> None:
    candidate = config().candidates[0]
    ambiguous = config().model_copy(
        update={"candidates": (candidate, candidate.model_copy(update={"ea_id": "another"}))}
    )
    result = attribute({"magic": 77, "symbol": "BTCUSDm"}, ambiguous)
    assert result.confidence == "AMBIGUOUS" and result.source == "UNKNOWN"
    probable = config().model_copy(
        update={"candidates": (candidate.model_copy(update={"exclusive_binding": False}),)}
    )
    assert attribute({"magic": 77, "symbol": "BTCUSDm"}, probable).source == "UNKNOWN"
    assert attribute({"magic": 0, "symbol": "BTCUSDm"}, config()).source == "UNKNOWN"


@pytest.mark.parametrize("side", [0, 1])
def test_fills_scale_partial_close_replay_and_deduplication(side: int) -> None:
    opening = trade(1, 1, type=side)
    more = trade(2, 2, type=side)
    partial = trade(3, 3, type=1 - side, entry=1, volume=".05", price="101", profit=".05")
    closing = trade(4, 4, type=1 - side, entry=1, volume=".15", price="102", profit=".30")
    frames = (
        frame(1, deals=(opening,)),
        frame(2, deals=(opening, more)),
        frame(3, deals=(partial,)),
        frame(4, deals=(closing,)),
    )
    events, episodes = replay(session(), frames)
    assert [e["kind"] for e in events if e["kind"].startswith("POSITION_")] == [
        "POSITION_OPENED",
        "POSITION_INCREASED",
        "POSITION_REDUCED",
        "POSITION_CLOSED",
    ]
    assert len(episodes) == 1 and episodes[0]["ea_metrics_eligible"]
    assert episodes[0]["holding_seconds"] == "3.0"
    assert episodes[0]["partial_close_count"] == 1
    assert episodes[0]["net_observed_pnl"] == "0.31"
    assert replay(session(), frames) == (events, episodes)
    assert summarize(episodes, events)["completed_episodes"] == 1


@pytest.mark.parametrize("field,kind", [("sl", "STOP_LOSS_CHANGED"), ("tp", "TAKE_PROFIT_CHANGED")])
def test_stop_changes_removals_and_recovered_time(field: str, kind: str) -> None:
    p = position()
    frames = (
        frame(1, positions=(p,)),
        frame(2, positions=({**p, field: "97"},), recovered=True),
        frame(3, positions=({**p, field: "0"},)),
    )
    events, _ = replay(session(), frames)
    changes = [e for e in events if e["kind"] == kind]
    assert [e["values"]["change"] for e in changes] == ["INITIAL", "CHANGED", "REMOVED"]
    assert changes[1]["recovered_state"] and changes[1]["broker_at"] is None
    assert changes[1]["values"]["time_basis"] == "FIRST_OBSERVED_AT"


def test_reversal_is_mixed_position_episode_not_fake_fee_allocation() -> None:
    events, episodes = replay(
        session(),
        (
            frame(1, deals=(trade(1, 1),)),
            frame(2, deals=(trade(2, 2, entry=2, type=1, volume=".2"),)),
        ),
    )
    assert any(e["kind"] == "POSITION_REVERSED" for e in events)
    assert episodes[0]["direction"] == "MIXED_REVERSAL"
    assert not episodes[0]["ea_metrics_eligible"]


def test_disappeared_position_without_deal_is_not_fabricated_close() -> None:
    events, _ = replay(session(), (frame(1, positions=(position(),)), frame(2)))
    assert any(e["kind"] == "POSITION_REMOVED_OBSERVED" for e in events)
    assert not any(e["kind"] == "POSITION_CLOSED" for e in events)


def test_missing_opening_and_unknown_source_excluded() -> None:
    events, episodes = replay(session(), (frame(1, deals=(trade(1, 1, entry=1, type=1),)),))
    assert any(e["kind"] == "RECOVERED_STATE" for e in events) and not episodes
    _, episodes = replay(session(), (frame(1, deals=(trade(1, 1, magic=0),)),))
    assert not episodes[0]["ea_metrics_eligible"]


def test_recovered_exit_uses_known_prior_position_but_not_invented_entry_time() -> None:
    events, episodes = replay(
        session(),
        (
            frame(1, positions=(position(),)),
            frame(2, deals=(trade(1, 2, entry=1, type=1),), recovered=True),
        ),
    )
    assert any(e["kind"] == "POSITION_CLOSED" and e["recovered_state"] for e in events)
    assert episodes[0]["opening_time_basis"] == "UNKNOWN_ENTRY_TIME"
    assert episodes[0]["opened_at"] is None
    assert episodes[0]["origin"] == "PREEXISTING"
    assert episodes[0]["holding_seconds"] is None
    assert not episodes[0]["ea_metrics_eligible"]


def test_simultaneous_hedging_positions_not_merged() -> None:
    _, episodes = replay(
        session(), (frame(1, deals=(trade(1, 1), trade(2, 1, position_id=200, type=1))),)
    )
    assert len(episodes) == 2
    with pytest.raises(ValueError, match="NETTING"):
        replay(
            session().model_copy(update={"margin_mode": 0}),
            (frame(1, positions=(position(), {**position(), "identifier": 200, "ticket": 200})),),
        )


def test_conflicting_ticket_and_future_deal_fail_closed() -> None:
    with pytest.raises(ValueError, match="CONFLICTING"):
        replay(
            session(), (frame(1, deals=(trade(1, 1),)), frame(2, deals=(trade(1, 1, price="200"),)))
        )
    with pytest.raises(ValueError, match="FUTURE"):
        replay(session(), (frame(1, deals=(trade(1, 10),)),))


@pytest.mark.parametrize("timeframe", list(TIMEFRAMES))
def test_no_future_or_incomplete_candle_leakage(timeframe: str) -> None:
    seconds = TIMEFRAMES[timeframe][1]
    at = T + timedelta(seconds=seconds)
    bars = (
        {"time": int(T.timestamp()), "open": "100", "high": "101", "low": "99", "close": "100"},
        {"time": int(at.timestamp()), "open": "100", "high": "101", "low": "99", "close": "100"},
    )
    context, windows = build_context(
        "BTCUSDm",
        at,
        {"time": int(at.timestamp()) + 1, "bid": "100", "ask": "101"},
        {timeframe: bars},
        50,
    )
    assert context["quote"] is None
    window = windows[context["windows"][timeframe]["window_id"]]
    assert len(window["bars"]) == 1


def test_safety_explicit_sdk_allowlist_no_proprietary_binary_access() -> None:
    allowed = READ_METHODS | CALCULATION_METHODS | {"copy_rates_range"}
    for path in Path("src/trading_ecosystem/observer").glob("*.py"):
        source = path.read_text()
        assert "order_" + "send" not in source and "order_check" not in source
        assert ".ex5" not in source.lower() and "MetaTrader5" not in source
        for node in ast.walk(ast.parse(source)):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "_sdk"
            ):
                assert node.attr in allowed


def test_registry_rejects_duplicate_candidate_ids() -> None:
    c = Candidate(ea_id="same", display_name="A", magic_numbers=(1,), symbols=("S",))
    with pytest.raises(ValueError, match="DUPLICATE_EA"):
        Config(symbols=("S",), candidates=(c, c))


@pytest.mark.parametrize("confirmed", [False, True])
def test_missing_polls_partial_close_requires_deal(confirmed: bool) -> None:
    events, _ = replay(
        session(),
        (
            frame(1, positions=({**position(), "volume": "1.00"},)),
            frame(
                2,
                positions=({**position(), "volume": "0.40"},),
                recovered=True,
                deals=(trade(2, 2, entry=1, type=1, volume="0.60"),) if confirmed else (),
            ),
        ),
    )
    reduced = [e for e in events if e["kind"] == "POSITION_REDUCED"]
    assert bool(reduced) == confirmed
    if confirmed:
        assert reduced[0]["values"]["closed_volume"] == "0.60"
    else:
        assert any(e["kind"] == "RECOVERED_STATE" for e in events)


@pytest.mark.parametrize("field,kind", [("sl", "STOP_LOSS_CHANGED"), ("tp", "TAKE_PROFIT_CHANGED")])
def test_nullable_stop_lifecycle(field: str, kind: str) -> None:
    events, episodes = replay(
        session(),
        tuple(
            frame(i + 1, positions=({**position(), field: value},))
            for i, value in enumerate((None, "95", "96", None))
        ),
    )
    changes = [e for e in events if e["kind"] == kind]
    assert [e["values"]["new_value"] for e in changes] == ["95", "96", None]
    assert changes[-1]["values"]["change"] == "REMOVED"
    assert all(e["broker_at"] is None for e in changes)
    summarize(episodes, events)


def test_netting_flat_then_short_separate_episodes_and_reversal_quantities() -> None:
    netting = session().model_copy(update={"margin_mode": 0})
    events, episodes = replay(
        netting,
        (
            frame(1, deals=(trade(1, 1),)),
            frame(2, deals=(trade(2, 2, type=1, entry=1),)),
            frame(3, deals=(trade(3, 3, type=1),)),
        ),
    )
    assert len(episodes) == 2
    assert {e["direction"] for e in episodes} == {"BUY", "SELL"}
    assert sum(e["kind"] == "POSITION_CLOSED" for e in events) == 1
    events, _ = replay(
        netting,
        (
            frame(1, deals=(trade(1, 1),)),
            frame(2, deals=(trade(2, 2, type=1, entry=2, volume=".30"),)),
        ),
    )
    reversal = next(e for e in events if e["kind"] == "POSITION_REVERSED")
    assert reversal["values"]["closed_volume"] == "0.10"
    assert reversal["values"]["opened_volume"] == "0.20"


def test_comment_binding_disambiguates_shared_magic() -> None:
    candidate = config().candidates[0]
    registry = config().model_copy(
        update={
            "candidates": (
                candidate.model_copy(update={"comment": "A"}),
                candidate.model_copy(update={"ea_id": "b", "comment": "B"}),
            )
        }
    )
    assert (
        attribute({"magic": 77, "symbol": "BTCUSDm", "comment": "A"}, registry).candidate_id
        == candidate.ea_id
    )
    assert attribute({"magic": 77, "symbol": "BTCUSDm"}, registry).source == "UNKNOWN"


def test_partial_duration_and_missing_financial_counts() -> None:
    events, episodes = replay(
        session(),
        (
            frame(1, positions=(position(),)),
            frame(2, deals=(trade(2, 2, type=1, entry=1),)),
        ),
    )
    summary = summarize(episodes, events)
    assert summary["unknown_duration_count"] == 1
    assert summary["known_duration_count"] == 0
    assert summary["gross_pnl"] is None
    events, episodes = replay(
        session(),
        (
            frame(1, deals=(trade(1, 1, profit=None),)),
            frame(2, deals=(trade(2, 2, type=1, entry=1),)),
        ),
    )
    summary = summarize(episodes, events)
    assert summary["gross_pnl_unknown_count"] == 1
    assert summary["gross_pnl"] is None
