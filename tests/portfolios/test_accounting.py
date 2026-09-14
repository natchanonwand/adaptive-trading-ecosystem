from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from trading_ecosystem.benchmarks.contracts import BenchmarkId
from trading_ecosystem.benchmarks.hashing import benchmark_definition_sha256, registry_sha256
from trading_ecosystem.benchmarks.registry import REGISTRY
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.primitives import Asset
from trading_ecosystem.portfolios.accounting import drawdown, r_analysis
from trading_ecosystem.portfolios.contracts import ASSET_ORDER, SCENARIO, Episode, Interval
from trading_ecosystem.portfolios.events import common_interval, concurrency, events
from trading_ecosystem.portfolios.evidence import (
    build,
    validate_input_set,
    verify_outputs,
    write_exclusive,
)
from trading_ecosystem.portfolios.synthetic import synthetic
from trading_ecosystem.simulation.hashing import digest

BASE = datetime(2024, 1, 1, tzinfo=UTC)
WINDOW = Interval(start=BASE, end=BASE + timedelta(hours=100))


def ep(
    asset: Asset = Asset.BTCUSD, entry: int = 1, exit: int | None = 2, value: str | None = "2"
) -> Episode:
    return Episode(
        episode_id=digest([asset.value, entry, exit, value]),
        asset=asset,
        benchmark_id=BenchmarkId.B01,
        signal_time=BASE + timedelta(hours=entry, seconds=-1),
        entry_time=BASE + timedelta(hours=entry),
        exit_time=BASE + timedelta(hours=exit) if exit is not None else None,
        gross_price_R=D(value) if value is not None else None,
        entry_sequence=2,
        exit_priority=60 if exit is not None else None,
        exit_sequence=5 if exit is not None else None,
    )


def test_common_interval_and_exact_calendar_cuts() -> None:
    interval = common_interval(
        (
            WINDOW,
            Interval(start=BASE - timedelta(hours=5), end=BASE + timedelta(hours=200)),
            Interval(start=BASE + timedelta(hours=10), end=BASE + timedelta(hours=110)),
        )
    )
    assert interval.start == BASE + timedelta(hours=10) and interval.end == WINDOW.end
    assert interval.cuts() == (BASE + timedelta(hours=64), BASE + timedelta(hours=82))
    assert interval.split(interval.cuts()[0]) == "Validation"
    assert interval.split(interval.cuts()[1]) == "Locked OOS"
    with pytest.raises(ValueError):
        Interval(start=BASE, end=BASE + timedelta(microseconds=1)).cuts()


def test_chronological_and_asset_order_source_priorities() -> None:
    episodes = tuple(ep(asset) for asset in reversed(ASSET_ORDER))
    merged = events(episodes)
    assert [event[-1].asset for event in merged[:3]] == list(ASSET_ORDER)
    assert [event[-2] for event in merged] == ["ENTRY"] * 3 + ["EXIT"] * 3
    same_time = ep(exit=1)
    assert [event[-2] for event in events((same_time,))] == ["ENTRY", "EXIT"]
    assert events(tuple(reversed(episodes))) == merged


def test_concurrency_and_time_event_distributions() -> None:
    result = concurrency(tuple(ep(asset) for asset in ASSET_ORDER), WINDOW)
    assert result["max_concurrent_episodes"] == result["max_concurrent_initial_risk_units"] == 3
    assert result["max_same_asset_concurrency"] == 1
    assert sum(result["time_microseconds_distribution"].values()) == 100 * 3600000000
    assert result["time_microseconds_distribution"]["3"] == 3600000000
    assert result["post_event_count_distribution"] == {"0": 1, "1": 2, "2": 2, "3": 1}


def test_same_asset_and_duplicate_episode_integrity_failures() -> None:
    with pytest.raises(ValueError, match="SAME_ASSET"):
        concurrency((ep(exit=5), ep(entry=2, exit=6)), WINDOW)
    with pytest.raises(ValueError, match="DUPLICATE_EPISODE"):
        events((ep(), ep()))


def test_r_arithmetic_periods_contribution_splits_and_drawdown() -> None:
    episodes = (
        ep(entry=1, exit=2, value="2"),
        ep(Asset.XAUUSD, 3, 4, "-1"),
        ep(Asset.USTEC100, 5, 6, "-2"),
        ep(entry=7, exit=8, value="3"),
    )
    result = r_analysis(episodes, WINDOW)
    assert result["total_gross_R"] == 2 and result["mean_R"] == D("0.5")
    assert result["median_R"] == D("0.5")
    assert result["wins"] == result["losses"] == 2 and result["win_rate"] == D("0.5")
    with arithmetic_context():
        assert result["profit_factor"]["value"] == D(5) / 3
    assert result["drawdown"]["maximum_drawdown"] == -3
    assert result["drawdown"]["maximum_duration_events"] == 3
    assert result["drawdown"]["maximum_duration_microseconds"] == 6 * 3600000000
    assert result["drawdown"]["max_recovered_trough_to_peak_microseconds"] == 2 * 3600000000
    assert result["contributions"]["BTCUSD"]["R"] == 5
    assert result["contributions"]["BTCUSD"]["percentage_of_positive_total"] == 250
    assert result["annual"]["2024"]["total"] == result["monthly"]["2024-01"]["total"] == 2
    assert result["splits"]["Development"]["total_gross_R"] == 2
    assert result["maximum_losing_streak"] == 2


@pytest.mark.parametrize(
    "values,state",
    [([], "UNDEFINED"), (["0"], "UNDEFINED"), (["2"], "POSITIVE_INFINITY"), (["-1"], "FINITE")],
)
def test_r_pf_and_nonpositive_contribution_semantics(values: list[str], state: str) -> None:
    episodes = tuple(
        ep(entry=1 + index * 2, exit=2 + index * 2, value=value)
        for index, value in enumerate(values)
    )
    result = r_analysis(episodes, WINDOW)
    assert result["profit_factor"]["state"] == state
    if result["total_gross_R"] <= 0:
        assert all(
            item["percentage_of_positive_total"] is None
            for item in result["contributions"].values()
        )


def test_cross_split_owned_once_by_decision() -> None:
    episode = ep(entry=60, exit=90)
    result = r_analysis((episode,), WINDOW)
    assert result["cross_split_episode_count"] == 1
    assert result["splits"]["Development"]["episodes"] == 1
    assert result["splits"]["Locked OOS"]["episodes"] == 0


def test_negative_and_zero_months_retained_and_exit_bucketing() -> None:
    interval = Interval(start=BASE, end=BASE + timedelta(days=70))
    episode = ep(entry=1, exit=24 * 40, value="-1")
    result = r_analysis((episode,), interval)
    assert result["monthly"]["2024-01"]["total"] == 0
    assert result["monthly"]["2024-02"]["total"] == -1
    assert result["monthly"]["2024-03"]["episodes"] == 0
    assert result["annual"]["2024"]["total"] == -1


def test_unrecovered_drawdown_is_censored() -> None:
    with arithmetic_context():
        result = drawdown([(BASE + timedelta(hours=1), D("-1"))], BASE, WINDOW.end)
    assert result["maximum_drawdown"] == -1
    assert result["spells"][0]["recovered"] is False
    assert result["spells"][0]["recovery_time"] is None
    assert result["maximum_duration_microseconds"] == 100 * 3600000000


def test_synthetic_initial_risk_plus_two_and_minus_one_compounding() -> None:
    result = synthetic((ep(), ep(entry=3, exit=4, value="-1")), WINDOW)
    assert result["starting_equity"] == 300
    assert result["ledger"][0]["risk_cash_at_entry"] == D("0.75")
    assert result["ledger"][1]["gross_cash_pnl"] == D("1.50")
    assert result["ledger"][2]["risk_cash_at_entry"] == D("0.75375")
    assert result["ending_realized_equity"] == D("300.74625")
    assert result["drawdown"]["maximum_drawdown"] == D("-0.75375")
    assert result["wins"] == result["losses"] == 1
    assert result["annual"]["2024"]["total"] == result["gross_synthetic_pnl"]


def test_open_risk_cash_remains_fixed_when_other_episode_changes_equity() -> None:
    result = synthetic((ep(exit=5), ep(Asset.XAUUSD, 2, 3, "2")), WINDOW)
    exits = [item for item in result["ledger"] if item["event"] == "EXIT"]
    assert exits[-1]["risk_cash_at_entry"] == D("0.75")
    assert result["ending_realized_equity"] == D("303")


def test_three_simultaneous_entries_and_cap() -> None:
    result = synthetic(tuple(ep(asset) for asset in ASSET_ORDER), WINDOW)
    assert result["max_reserved_risk_usd"] == D("2.25")
    assert result["max_reserved_risk_fraction"] == D("0.0075")
    assert result["risk_rejections"] == 0
    assert result["ending_realized_equity"] == D("304.5")


def test_cap_rejection_after_loss_preserves_underlying_r_outcomes() -> None:
    episodes = (
        ep(exit=8),
        ep(Asset.XAUUSD, 1, 9),
        ep(Asset.USTEC100, 1, 2, "-1"),
        ep(Asset.USTEC100, 3, 4),
    )
    result = synthetic(episodes, WINDOW)
    rejections = [item for item in result["ledger"] if item["event"] == "SYNTHETIC_RISK_REJECTED"]
    assert len(rejections) == result["risk_rejections"] == 1
    assert rejections[0]["reason"] == "AGGREGATE_RESERVED_RISK_CAP"
    assert result["ending_realized_equity"] == D("302.25")
    assert r_analysis(episodes, WINDOW)["episodes"] == 4


def test_open_boundary_has_no_invented_cash_result() -> None:
    result = synthetic((ep(exit=None, value=None),), WINDOW)
    assert result["ending_realized_equity"] == 300 and result["open_accepted_episodes"] == 1
    assert result["drawdown"]["maximum_drawdown"] == 0
    assert len(result["ledger"]) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("risk_fraction", "0.005"),
        ("initial_equity_usd", "500"),
        ("max_concurrent", 4),
        ("max_per_asset", 2),
        ("aggregate_risk_cap", "0.01"),
        ("direction", "SHORT_ONLY"),
    ],
)
def test_no_extra_scenarios_or_mutation(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        SCENARIO.model_copy(update={field: value})


def inputs() -> list[dict[str, Any]]:
    results = []
    for asset in ASSET_ORDER:
        for definition in REGISTRY.definitions:
            episode = ep(asset)
            record: dict[str, Any] = {
                "asset": asset,
                "benchmark_id": definition.benchmark_id,
                "signal_time": episode.signal_time.isoformat(),
                "entry_time": episode.entry_time.isoformat(),
                "exit_time": episode.exit_time.isoformat() if episode.exit_time else None,
                "gross_price_R": "2",
                "simulation_result": {
                    "events": [
                        {"entry": {}, "exit": None, "kind": 30, "sequence": 2},
                        {"entry": None, "exit": {}, "kind": 60, "sequence": 5},
                    ]
                },
            }
            results.append(
                {
                    "asset": asset.value,
                    "benchmark_id": definition.benchmark_id.value,
                    "benchmark_definition_hash": benchmark_definition_sha256(definition),
                    "registry_sha256": registry_sha256(),
                    "result_sha256": digest(record),
                    "records": [record],
                }
            )
    return results


def test_exact_twelve_inputs_four_same_strategy_portfolios() -> None:
    source = inputs()
    for invalid in (source[:-1], source + source[:1], source[:-1] + source[:1]):
        with pytest.raises(ValueError):
            validate_input_set(invalid)
    outputs = build(source, WINDOW)
    assert len(outputs) == 8
    assert [item["portfolio_id"] for item in outputs[::2]] == [
        "PORTFOLIO_B01",
        "PORTFOLIO_B02",
        "PORTFOLIO_B03",
        "PORTFOLIO_B04",
    ]
    assert all(item["analysis"]["episodes"] == 3 for item in outputs[::2])
    assert all(item["analysis"]["ending_realized_equity"] == "304.5" for item in outputs[1::2])


def test_pre_common_exclusion_and_deterministic_identity_replay(tmp_path: Path) -> None:
    source = inputs()
    interval = Interval(start=BASE + timedelta(hours=3), end=WINDOW.end)
    outputs = build(source, interval)
    assert all(item["analysis"]["episodes"] == 0 for item in outputs[::2])
    assert all(
        item["pre_common_excluded"] == {"BTCUSD": 1, "XAUUSD": 1, "USTEC100": 1} for item in outputs
    )
    expected = build(source, WINDOW)
    with localcontext() as context:
        context.prec = 6
        assert build(list(reversed(source)), WINDOW) == expected
    for item in expected:
        write_exclusive(tmp_path / (item["portfolio_id"] + "--" + item["layer"] + ".json"), item)
    assert verify_outputs(tmp_path, expected) == expected
    path = next(tmp_path.glob("*.json"))
    before = path.read_bytes()
    path.write_bytes(before + b" ")
    with pytest.raises(ValueError):
        verify_outputs(tmp_path, expected)
