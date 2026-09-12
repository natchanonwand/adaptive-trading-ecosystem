from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from trading_ecosystem.benchmarks.contracts import BenchmarkId
from trading_ecosystem.benchmarks.registry import get_definition
from trading_ecosystem.simulation import simulate
from trading_ecosystem.simulation.contracts import (
    CostModel,
    EntryIntent,
    EventKind,
    ExitReason,
    PriceIncrement,
    ResultStatus,
    SimulationBar,
    SimulationSpec,
    StrategyExitIntent,
)
from trading_ecosystem.simulation.hashing import result_sha256, specification_sha256

BASE = datetime(2024, 1, 1, tzinfo=UTC)


def bar(
    index: int, open: str = "100", high: str = "105", low: str = "95", close: str = "100"
) -> SimulationBar:
    return SimulationBar(
        open_time=BASE + timedelta(hours=index),
        close_time=BASE + timedelta(hours=index + 1),
        open=D(open),
        high=D(high),
        low=D(low),
        close=D(close),
    )


def costs(**updates: object) -> CostModel:
    return CostModel.model_validate(
        {
            "entry_spread_price": "0",
            "entry_slippage_price": "0",
            "exit_spread_price": "0",
            "exit_slippage_price": "0",
            "commission_cash": "0",
            "financing_cash": "0",
            **updates,
        }
    )


def fixture(benchmark: BenchmarkId = BenchmarkId.B01, **updates: object) -> SimulationSpec:
    return SimulationSpec.model_validate(
        {
            "benchmark": get_definition(benchmark),
            "bars": (bar(0), bar(1)),
            "entry_intent": EntryIntent(
                benchmark_id=benchmark,
                decision_time=bar(0).close_time,
                available_at=bar(0).close_time,
                signal_stop_raw=D("90"),
            ),
            "increment": PriceIncrement(tick_size=D("1")),
            "costs": costs(),
            **updates,
        }
    )


def exit_intent(benchmark: BenchmarkId, index: int = 1) -> StrategyExitIntent:
    return StrategyExitIntent(
        benchmark_id=benchmark,
        decision_time=bar(index).close_time,
        available_at=bar(index).close_time,
    )


def test_next_open_components_actual_fill_risk_and_target() -> None:
    spec = fixture(
        bars=(bar(0), bar(1, "110", "115", "105", "111")),
        costs=costs(entry_spread_price="1", entry_slippage_price="2"),
    )
    result = simulate(spec)
    position = result.position
    assert position is not None and position.target is not None
    assert position.entry.reference_open == 110 and position.entry.entry_fill == 113
    assert position.entry.spread_component == 1 and position.entry.adverse_slippage_component == 2
    assert position.entry.price_reference_time == spec.entry_intent.decision_time
    assert position.entry.modeled_execution_time == spec.entry_intent.decision_time + timedelta(
        microseconds=1
    )
    assert position.initial_price_risk == 23 and position.target.target_raw == 159
    assert position.target.target != 120  # signal close 100 would incorrectly produce 120
    assert position.stop.fixed_stop == 90
    assert [event.kind for event in result.events[:5]] == [
        EventKind.SIGNAL_DECISION,
        EventKind.ENTRY_INTENT,
        EventKind.ENTRY_FILL,
        EventKind.PROTECTIVE_STOP_ACTIVE,
        EventKind.TAKE_PROFIT_ACTIVE,
    ]


def test_clock_gap_execution_never_precedes_price_reference() -> None:
    result = simulate(fixture(bars=(bar(0), bar(9))))
    assert result.position is not None
    assert result.position.entry.price_reference_time == bar(9).open_time
    assert result.position.entry.modeled_execution_time == bar(9).open_time + timedelta(
        microseconds=1
    )


def test_no_future_bar_never_uses_signal_close() -> None:
    result = simulate(fixture(bars=(bar(0),)))
    assert result.status == ResultStatus.NO_FILL_END_OF_DATA
    assert result.position is None and result.episode is None
    assert all(event.entry is None for event in result.events)


@pytest.mark.parametrize("opening", ["89", "90"])
def test_invalid_initial_risk_opens_no_position(opening: str) -> None:
    result = simulate(fixture(bars=(bar(0), bar(1, opening, "95", "85", "90"))))
    assert result.status == ResultStatus.INVALID_INITIAL_PRICE_RISK
    assert result.position is None and result.episode is None
    assert EventKind.ENTRY_FILL not in [event.kind for event in result.events]


def test_explicit_tick_floor_and_ceiling() -> None:
    spec = fixture(
        increment=PriceIncrement(tick_size=D("0.25")), costs=costs(entry_slippage_price="0.01")
    )
    spec = spec.model_copy(
        update={
            "entry_intent": spec.entry_intent.model_copy(update={"signal_stop_raw": D("90.24")})
        }
    )
    result = simulate(spec)
    assert result.position is not None and result.position.target is not None
    assert result.position.stop.fixed_stop == 90
    assert result.position.target.target_raw == D("120.03")
    assert result.position.target.target == D("120.25")


@pytest.mark.parametrize("benchmark", [BenchmarkId.B02, BenchmarkId.B03, BenchmarkId.B04])
def test_no_target_for_trend_benchmarks(benchmark: BenchmarkId) -> None:
    result = simulate(fixture(benchmark))
    assert result.position is not None and result.position.target is None
    assert result.position.direction == "LONG_ONLY" and result.position.synthetic_unit_quantity == 1


@pytest.mark.parametrize(
    "open,high,low,close,reason,price,gap,ambiguous",
    [
        ("85", "130", "80", "100", ExitReason.STOP_LOSS, "85", True, False),
        ("90", "130", "80", "100", ExitReason.STOP_LOSS, "90", True, False),
        ("125", "130", "80", "100", ExitReason.TAKE_PROFIT, "120", True, False),
        ("120", "130", "80", "100", ExitReason.TAKE_PROFIT, "120", True, False),
        ("100", "110", "90", "100", ExitReason.STOP_LOSS, "90", False, False),
        ("100", "120", "95", "100", ExitReason.TAKE_PROFIT, "120", False, False),
        ("100", "120", "90", "100", ExitReason.STOP_LOSS, "90", False, True),
        ("100", "150", "50", "100", ExitReason.STOP_LOSS, "90", False, True),
    ],
)
def test_gap_and_intrabar_precedence(
    open: str,
    high: str,
    low: str,
    close: str,
    reason: ExitReason,
    price: str,
    gap: bool,
    ambiguous: bool,
) -> None:
    result = simulate(fixture(bars=(bar(0), bar(1), bar(2, open, high, low, close))))
    assert result.episode is not None
    exit = result.episode.exit
    assert exit.reason == reason and exit.exit_price == D(price)
    assert exit.gap_exit is gap and exit.intrabar_ambiguous is ambiguous
    assert result.episode.position.stop.fixed_stop == 90
    assert result.episode.gross_price_R == (D(price) - 100) / 10


@pytest.mark.parametrize("benchmark", list(BenchmarkId))
def test_entry_bar_is_exposed_to_intrabar_stop(benchmark: BenchmarkId) -> None:
    result = simulate(fixture(benchmark, bars=(bar(0), bar(1, low="89"))))
    assert result.episode is not None and result.episode.exit.reason == ExitReason.STOP_LOSS
    assert (
        result.episode.exit.modeled_execution_time
        > result.episode.position.entry.modeled_execution_time
    )


@pytest.mark.parametrize("benchmark", [BenchmarkId.B02, BenchmarkId.B03, BenchmarkId.B04])
def test_strategy_exit_next_open_precedes_current_gap_and_intrabar(benchmark: BenchmarkId) -> None:
    result = simulate(
        fixture(
            benchmark,
            bars=(bar(0), bar(1), bar(2, "80", "140", "70", "110")),
            strategy_exits=(exit_intent(benchmark),),
        )
    )
    assert result.episode is not None
    exit = result.episode.exit
    assert exit.reason == (
        ExitReason.TREND_EXIT if benchmark == BenchmarkId.B02 else ExitReason.CHANNEL_EXIT
    )
    assert exit.exit_price == 80 and exit.price_source == "NEXT_OBSERVED_BAR_OPEN"
    assert exit.decision_time == bar(1).close_time
    assert exit.modeled_execution_time == bar(2).open_time + timedelta(microseconds=1)
    assert not exit.gap_exit and not exit.intrabar_ambiguous


@pytest.mark.parametrize("benchmark", [BenchmarkId.B02, BenchmarkId.B03, BenchmarkId.B04])
def test_stop_before_close_prevents_retroactive_strategy_exit(benchmark: BenchmarkId) -> None:
    result = simulate(
        fixture(
            benchmark,
            bars=(bar(0), bar(1, low="89"), bar(2)),
            strategy_exits=(exit_intent(benchmark),),
        )
    )
    assert result.episode is not None and result.episode.exit.reason == ExitReason.STOP_LOSS
    assert EventKind.STRATEGY_EXIT_DECISION not in [event.kind for event in result.events]


def test_boundary_open_pending_and_explicit_exception() -> None:
    spec = fixture(BenchmarkId.B02, strategy_exits=(exit_intent(BenchmarkId.B02),))
    result = simulate(spec)
    assert result.status == ResultStatus.OPEN_AT_EVALUATION_BOUNDARY and result.episode is None
    assert result.pending_strategy_exit == spec.strategy_exits[0]
    flat = simulate(spec.model_copy(update={"flatten_at_boundary": True}))
    assert flat.episode is not None and flat.episode.exit.reason == ExitReason.EVALUATION_BOUNDARY
    assert (
        flat.episode.exit.price_source == "BOUNDARY_CLOSE" and flat.episode.exit.exit_price == 100
    )
    assert flat.pending_strategy_exit is None
    assert flat.events[-1].kind == EventKind.EVALUATION_BOUNDARY


def test_costs_are_separate_do_not_retarget_or_change_gross_price_r() -> None:
    spec = fixture(bars=(bar(0), bar(1, high="120")))
    plain = simulate(spec)
    expensive = simulate(
        spec.model_copy(
            update={
                "costs": costs(
                    exit_spread_price="2",
                    exit_slippage_price="3",
                    commission_cash="7",
                    financing_cash="-1",
                )
            }
        )
    )
    assert plain.episode is not None and expensive.episode is not None
    assert expensive.episode.position.target == plain.episode.position.target
    assert expensive.episode.gross_price_R == plain.episode.gross_price_R == 2
    assert expensive.episode.exit.exit_price == 120
    assert expensive.episode.exit.spread_component == 2
    assert expensive.episode.exit.adverse_slippage_component == 3
    assert (
        expensive.episode.costs.commission_cash == 7
        and expensive.episode.costs.financing_cash == -1
    )
    assert expensive.episode.monetary_net_R is None


def test_future_bars_cannot_change_prior_fills_and_completed_events() -> None:
    spec = fixture(bars=(bar(0), bar(1, high="120"), bar(2)))
    original = simulate(spec)
    changed = simulate(
        spec.model_copy(
            update={"bars": (bar(0), bar(1, high="120"), bar(2, "300", "500", "1", "400"))}
        )
    )
    assert changed.events == original.events and changed.episode == original.episode
    assert changed.specification_sha256 != original.specification_sha256
    prefix = simulate(fixture())
    extended = simulate(fixture(bars=(bar(0), bar(1), bar(2, high="120"))))
    assert prefix.events[:-1] == extended.events[: len(prefix.events) - 1]


def test_future_strategy_eligibility_cannot_replace_prior_stop() -> None:
    spec = fixture(BenchmarkId.B02, bars=(bar(0), bar(1, low="89"), bar(2)))
    original = simulate(spec)
    changed = simulate(
        spec.model_copy(update={"strategy_exits": (exit_intent(BenchmarkId.B02, 2),)})
    )
    assert original.events == changed.events and original.episode == changed.episode


def test_determinism_decimal_context_scale_environment_and_input_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = fixture(bars=(bar(0), bar(1, high="120")))
    expected = simulate(spec)
    with localcontext() as ctx:
        ctx.prec = 5
        ctx.rounding = "ROUND_DOWN"
        assert simulate(spec) == expected
        assert result_sha256(simulate(spec)) == result_sha256(expected)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPUTERNAME", "synthetic-other")
    assert result_sha256(simulate(spec)) == result_sha256(expected)
    scaled = spec.model_copy(update={"increment": PriceIncrement(tick_size=D("1.00"))})
    assert specification_sha256(scaled) == specification_sha256(spec)
    assert result_sha256(simulate(scaled)) == result_sha256(expected)
    for update in (
        {"costs": costs(commission_cash="1")},
        {"increment": PriceIncrement(tick_size=D("0.5"))},
        {"flatten_at_boundary": True},
    ):
        assert specification_sha256(spec.model_copy(update=update)) != specification_sha256(spec)
    assert [event.sequence for event in expected.events] == list(range(len(expected.events)))
    assert list(expected.events) == sorted(
        expected.events, key=lambda event: (event.time, int(event.kind), event.bar_index)
    )


@pytest.mark.parametrize(
    "update",
    [
        {"open": "0"},
        {"open": 1.5},
        {"high": "99"},
        {"low": "101"},
        {"close_time": BASE},
        {"open_time": BASE.replace(minute=1)},
        {"qualification_eligible": True},
    ],
)
def test_invalid_bar_and_classification_rejected(update: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        bar(0).model_copy(update=update)


@pytest.mark.parametrize(
    "update",
    [
        {"bars": ()},
        {"bars": (bar(1), bar(0))},
        {"bars": (bar(0), bar(0))},
        {"flatten_at_boundary": "true"},
        {"quantity": 2},
        {"direction": "SHORT_ONLY"},
        {"entry_intents": ()},
        {"qualification_eligible": True},
        {"created_at": "now"},
    ],
)
def test_invalid_spec_and_unauthorized_capabilities_rejected(update: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        fixture().model_copy(update=update)


@pytest.mark.parametrize(
    "field",
    [
        "entry_spread_price",
        "entry_slippage_price",
        "exit_spread_price",
        "exit_slippage_price",
        "commission_cash",
    ],
)
def test_negative_costs_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        costs(**{field: "-1"})


def test_intent_provenance_timing_and_benchmark_validation() -> None:
    spec = fixture()
    for update in (
        {"available_at": BASE},
        {"available_at": BASE + timedelta(hours=2)},
        {"eligibility": "HOLD_OR_NO_ACTION"},
    ):
        with pytest.raises(ValidationError):
            spec.entry_intent.model_copy(update=update)
    with pytest.raises(ValidationError):
        fixture(BenchmarkId.B02, entry_intent=spec.entry_intent)
    with pytest.raises(ValidationError):
        exit_intent(BenchmarkId.B01)
    for intents in ((exit_intent(BenchmarkId.B03),), (exit_intent(BenchmarkId.B02),) * 2):
        with pytest.raises(ValidationError):
            fixture(BenchmarkId.B02, strategy_exits=intents)
    with pytest.raises(ValidationError):
        fixture(
            entry_intent=spec.entry_intent.model_copy(
                update={"decision_time": BASE, "available_at": BASE}
            )
        )


def test_output_and_nested_events_are_immutable() -> None:
    result = simulate(fixture())
    with pytest.raises(ValidationError):
        result.status = ResultStatus.COMPLETED  # type: ignore[misc]
    with pytest.raises(ValidationError):
        result.events[0].detail = "changed"  # type: ignore[misc]
    assert result.position is not None
    with pytest.raises(ValidationError):
        result.position.stop.fixed_stop = D("95")  # type: ignore[misc]
    with pytest.raises(TypeError):
        SimulationSpec.model_construct(**fixture().model_dump())


def test_output_contracts_reject_inconsistent_mechanics() -> None:
    result = simulate(fixture(bars=(bar(0), bar(1, high="120"))))
    episode = result.episode
    assert episode is not None and episode.position.target is not None
    position = episode.position
    for update in (
        {"entry_fill": D("101")},
        {"modeled_execution_time": BASE},
        {"price_reference_time": BASE},
    ):
        with pytest.raises(ValidationError):
            position.entry.model_copy(update=update)
    with pytest.raises(ValidationError):
        position.stop.model_copy(update={"fixed_stop": D("91")})
    with pytest.raises(ValidationError):
        episode.position.target.model_copy(update={"target": D("119")})
    with pytest.raises(ValidationError):
        position.model_copy(update={"initial_price_risk": D("11")})
    with pytest.raises(ValidationError):
        position.model_copy(update={"target": None})
    with pytest.raises(ValidationError):
        episode.model_copy(update={"gross_price_R": D("3")})
    with pytest.raises(ValidationError):
        episode.exit.model_copy(update={"intrabar_ambiguous": True})


def test_reference_fixture_event_order_independently_expected() -> None:
    result = simulate(fixture(bars=(bar(0), bar(1, high="120", low="90"))))
    opening = BASE + timedelta(hours=1, microseconds=1)
    assert [
        (event.sequence, event.kind.name, event.time, event.bar_index) for event in result.events
    ] == [
        (0, "SIGNAL_DECISION", BASE + timedelta(hours=1), 0),
        (1, "ENTRY_INTENT", BASE + timedelta(hours=1), 0),
        (2, "ENTRY_FILL", opening, 1),
        (3, "PROTECTIVE_STOP_ACTIVE", opening, 1),
        (4, "TAKE_PROFIT_ACTIVE", opening, 1),
        (5, "STOP_EXIT", BASE + timedelta(hours=2), 1),
    ]
    assert result.episode is not None
    assert result.episode.gross_price_R == -1
    assert result.episode.exit.intrabar_ambiguous is True
