from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tests.research.test_indicators import bars
from trading_ecosystem.benchmarks import (
    REGISTRY,
    BenchmarkId,
    EvaluationInput,
    ResearchObservation,
    evaluate,
    get_definition,
)
from trading_ecosystem.datasets.contracts import Bar
from trading_ecosystem.research import indicators as k

D = Decimal
BASE = datetime(2024, 1, 1, tzinfo=UTC)


def point(
    benchmark: BenchmarkId, count: int | None = None, **changes: object
) -> ResearchObservation:
    count = get_definition(benchmark).required_observations if count is None else count
    time = BASE + timedelta(hours=count)
    return ResearchObservation.model_validate(
        dict(
            benchmark_id=benchmark,
            observed_bar_count=count,
            bar_close_time=time,
            available_at=time,
            close=D(11),
            fast_ema=D(2),
            slow_ema=D(1),
            previous_high=D(10),
            previous_low=D(5),
        )
        | changes
    )


def decision(current: ResearchObservation, previous: ResearchObservation | None = None) -> str:
    return evaluate(
        EvaluationInput(
            current=current,
            previous=previous,
            decision_time=current.bar_close_time,
            bar_complete=True,
        )
    ).value


@pytest.mark.parametrize(
    "fast,slow,close,expected",
    [
        (2, 1, 11, "ENTRY_ELIGIBLE"),
        (1, 2, 11, "HOLD_OR_NO_ACTION"),
        (1, 1, 11, "HOLD_OR_NO_ACTION"),
        (2, 1, 10, "HOLD_OR_NO_ACTION"),
        (2, 1, 9, "HOLD_OR_NO_ACTION"),
    ],
)
def test_b01_conjunction_and_strict_equalities(
    fast: int, slow: int, close: int, expected: str
) -> None:
    assert (
        decision(point(BenchmarkId.B01, fast_ema=D(fast), slow_ema=D(slow), close=D(close)))
        == expected
    )


@pytest.mark.parametrize(
    "before,now,expected",
    [
        ((1, 2), (2, 1), "ENTRY_ELIGIBLE"),
        ((1, 1), (2, 1), "ENTRY_ELIGIBLE"),
        ((2, 1), (3, 1), "HOLD_OR_NO_ACTION"),
        ((2, 1), (1, 2), "EXIT_ELIGIBLE"),
        ((2, 1), (1, 1), "EXIT_ELIGIBLE"),
        ((1, 2), (1, 1), "HOLD_OR_NO_ACTION"),
        ((1, 1), (1, 1), "HOLD_OR_NO_ACTION"),
        ((1, 2), (1, 2), "HOLD_OR_NO_ACTION"),
    ],
)
def test_b02_cross_events(before: tuple[int, int], now: tuple[int, int], expected: str) -> None:
    previous = point(BenchmarkId.B02, 200, fast_ema=D(before[0]), slow_ema=D(before[1]))
    current = point(BenchmarkId.B02, 201, fast_ema=D(now[0]), slow_ema=D(now[1]), close=None)
    assert decision(current, previous) == expected


@pytest.mark.parametrize("benchmark", [BenchmarkId.B03, BenchmarkId.B04])
@pytest.mark.parametrize(
    "close,expected",
    [
        (11, "ENTRY_ELIGIBLE"),
        (4, "EXIT_ELIGIBLE"),
        (10, "HOLD_OR_NO_ACTION"),
        (5, "HOLD_OR_NO_ACTION"),
        (7, "HOLD_OR_NO_ACTION"),
    ],
)
def test_channel_strict_entry_exit(benchmark: BenchmarkId, close: int, expected: str) -> None:
    assert decision(point(benchmark, close=D(close))) == expected


@pytest.mark.parametrize("benchmark", list(BenchmarkId))
def test_warmup_and_completed_bar_only(benchmark: BenchmarkId) -> None:
    required = get_definition(benchmark).required_observations
    assert decision(point(benchmark, required - 1)) == "UNAVAILABLE"
    current = point(benchmark)
    assert (
        evaluate(
            EvaluationInput(
                current=current,
                decision_time=current.bar_close_time - timedelta(minutes=1),
                bar_complete=False,
            )
        )
        == "UNAVAILABLE"
    )
    with pytest.raises(ValidationError):
        EvaluationInput(
            current=current,
            decision_time=current.bar_close_time + timedelta(seconds=1),
            bar_complete=True,
        )
    delayed = current.model_copy(
        update={"available_at": current.bar_close_time + timedelta(seconds=1)}
    )
    assert decision(delayed) == "UNAVAILABLE"


@pytest.mark.parametrize("field", ["fast_ema", "slow_ema"])
def test_b02_unavailable_current_and_previous(field: str) -> None:
    current, previous = point(BenchmarkId.B02), point(BenchmarkId.B02, 200)
    assert decision(current) == "UNAVAILABLE"
    assert decision(current.model_copy(update={field: None}), previous) == "UNAVAILABLE"
    assert decision(current, previous.model_copy(update={field: None})) == "UNAVAILABLE"


@pytest.mark.parametrize(
    "benchmark,field",
    [
        (BenchmarkId.B01, "previous_high"),
        (BenchmarkId.B01, "fast_ema"),
        (BenchmarkId.B01, "close"),
        (BenchmarkId.B03, "previous_low"),
        (BenchmarkId.B04, "previous_high"),
    ],
)
def test_missing_research_inputs(benchmark: BenchmarkId, field: str) -> None:
    assert decision(point(benchmark, **{field: None})) == "UNAVAILABLE"


def test_previous_values_must_be_adjacent_available_and_in_the_past() -> None:
    current = point(BenchmarkId.B02)
    for previous in (
        point(BenchmarkId.B02, 202),
        point(BenchmarkId.B02, 199),
        point(BenchmarkId.B01, 200),
    ):
        with pytest.raises(ValidationError):
            decision(current, previous)
    previous = point(
        BenchmarkId.B02, 200, available_at=current.bar_close_time + timedelta(seconds=1)
    )
    assert decision(current, previous) == "UNAVAILABLE"
    # A clock gap is permitted; adjacency is counted in observed bars.
    previous = point(
        BenchmarkId.B02, 200, fast_ema=D(1), slow_ema=D(2), bar_close_time=BASE, available_at=BASE
    )
    assert decision(current, previous) == "ENTRY_ELIGIBLE"


def supplied_inputs(
    benchmark: BenchmarkId, observations: Sequence[Bar]
) -> tuple[EvaluationInput, ...]:
    definition = get_definition(benchmark)
    close = k.observed_closes(observations)
    entry = definition.entry_rule
    fast = k.ema(close, entry.fast_ema_period) if entry.fast_ema_period else (None,) * len(close)
    slow = k.ema(close, entry.slow_ema_period) if entry.slow_ema_period else (None,) * len(close)
    high = (
        k.previous_high(observations, entry.previous_high_period)
        if entry.previous_high_period
        else (None,) * len(close)
    )
    low_period = definition.exit_rule.previous_low_period
    low = k.previous_low(observations, low_period) if low_period else (None,) * len(close)
    result = []
    previous = None
    for index, bar in enumerate(observations):
        current = ResearchObservation(
            benchmark_id=benchmark,
            observed_bar_count=index + 1,
            bar_close_time=bar.close_time,
            available_at=bar.available_at,
            close=bar.close,
            fast_ema=fast[index],
            slow_ema=slow[index],
            previous_high=high[index],
            previous_low=low[index],
        )
        result.append(
            EvaluationInput(
                current=current, previous=previous, decision_time=bar.close_time, bar_complete=True
            )
        )
        previous = current
    return tuple(result)


@pytest.mark.parametrize("benchmark", list(BenchmarkId))
def test_phase31_composition_future_mutation_and_current_extrema_exclusion(
    benchmark: BenchmarkId,
) -> None:
    observations = bars(tuple(str(1000 - i if i < 210 else 2000 + i) for i in range(270)))
    inputs = supplied_inputs(benchmark, observations)
    original = tuple(evaluate(item) for item in inputs)
    cutoff = 255
    changed = observations[:cutoff] + tuple(
        bar.model_copy(update={"open": D(1), "close": D(1), "high": D(2), "low": D("0.5")})
        for bar in observations[cutoff:]
    )
    assert (
        tuple(evaluate(item) for item in supplied_inputs(benchmark, changed))[:cutoff]
        == original[:cutoff]
    )
    assert (
        tuple(evaluate(item) for item in supplied_inputs(benchmark, observations[:cutoff]))
        == original[:cutoff]
    )
    extreme = (
        observations[:cutoff]
        + (observations[cutoff].model_copy(update={"high": D(99999), "low": D("0.1")}),)
        + observations[cutoff + 1 :]
    )
    current = supplied_inputs(benchmark, extreme)[cutoff]
    assert current.current.previous_high == inputs[cutoff].current.previous_high
    assert current.current.previous_low == inputs[cutoff].current.previous_low
    assert evaluate(current) == original[cutoff]
    assert get_definition(benchmark) in REGISTRY.definitions
