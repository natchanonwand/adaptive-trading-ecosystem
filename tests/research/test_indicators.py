from collections.abc import Sequence
from dataclasses import FrozenInstanceError, asdict
from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal, Inexact, localcontext

import pytest

from trading_ecosystem.datasets.contracts import HOUR, Bar
from trading_ecosystem.domain.canonical import canonical_bytes
from trading_ecosystem.domain.primitives import Asset
from trading_ecosystem.research import indicators as k

D = Decimal
START = datetime(2024, 1, 1, tzinfo=UTC)


def bars(
    closes: Sequence[str] = ("10", "14", "8", "11"),
    highs: Sequence[str] | None = None,
    lows: Sequence[str] | None = None,
    offsets: Sequence[int] | None = None,
) -> tuple[Bar, ...]:
    result = []
    for index, close in enumerate(closes):
        time = START + HOUR * (index if offsets is None else offsets[index])
        result.append(
            Bar(
                dataset_id="synthetic-kernel",
                canonical_asset=Asset.BTCUSD,
                broker_symbol="BTCUSDm",
                instrument_metadata_reference="0" * 64,
                open_time=time,
                close_time=time + HOUR,
                available_at=time + HOUR,
                open=D(close),
                close=D(close),
                high=D(close if highs is None else highs[index]),
                low=D(close if lows is None else lows[index]),
                tick_volume=1,
                spread_points=0,
                real_volume=0,
                retrieved_at=START,
            )
        )
    return tuple(result)


def ranges_fixture() -> tuple[Bar, ...]:
    return bars(highs=("12", "15", "9", "12"), lows=("9", "13", "7", "10"))


def columns(observations: Sequence[Bar]) -> tuple[tuple[object, ...], ...]:
    close = k.observed_closes(observations)
    fast, slow = k.sma(close, 2), k.ema(close, 3)
    high, low = k.previous_high(observations, 2), k.previous_low(observations, 2)
    change = k.trailing_return(close, 2)
    return (
        fast,
        slow,
        k.true_range(observations),
        k.wilder_atr(observations, 2),
        high,
        low,
        change,
        k.gap_metadata(observations),
        tuple(k.moving_average_state(a, b) for a, b in zip(fast, slow, strict=True)),
        tuple(
            k.channel_breakout_state(c, h, low_)
            for c, h, low_ in zip(close, high, low, strict=True)
        ),
        tuple(k.momentum_state(value) for value in change),
    )


def test_sma_warmup_and_exact_trailing_windows() -> None:
    values = k.observed_closes(bars())
    assert k.sma(values, 2) == (None, D("12"), D("11"), D("9.5"))
    assert k.sma(values, 1) == values
    assert k.sma(values, 5) == (None,) * 4
    assert k.sma((D("0.1"), D("0.2")), 2) == (None, D("0.15"))


def test_ema_sma_seed_and_recursive_values() -> None:
    values = k.observed_closes(bars(("2", "4", "6", "10", "4")))
    expected = (None, None, D("4"), D("7"), D("5.5"))
    assert k.ema(values, 3) == expected
    assert k.ema(values, 3) == expected
    assert k.ema(values, 1) == values
    assert k.ema(values[:2], 3) == (None, None)


def test_true_range_first_high_low_gap_up_and_gap_down() -> None:
    # First: 12-9=3. Up: 15-10=5. Down: 14-7=7. Final: 12-8=4.
    assert k.true_range(ranges_fixture()) == (D("3"), D("5"), D("7"), D("4"))
    assert k.true_range(bars(("10", "10"), ("11", "12"), ("9", "8"))) == (D(2), D(4))


def test_wilder_atr_seed_warmup_and_recursion() -> None:
    assert k.wilder_atr(ranges_fixture(), 2) == (None, D("4"), D("5.5"), D("4.75"))
    assert k.wilder_atr(ranges_fixture(), 1) == k.true_range(ranges_fixture())
    assert k.wilder_atr(ranges_fixture(), 5) == (None,) * 4


def test_previous_extremes_exact_windows_exclude_current() -> None:
    observations = ranges_fixture()
    assert k.previous_high(observations, 2) == (None, None, D("15"), D("15"))
    assert k.previous_low(observations, 2) == (None, None, D("9"), D("7"))
    assert k.previous_high(observations, 1) == (None, D("12"), D("15"), D("9"))
    assert k.previous_low(observations, 1) == (None, D("9"), D("13"), D("7"))
    changed = (
        *observations[:2],
        observations[2].model_copy(update={"high": D("1000"), "low": D("1")}),
        observations[3],
    )
    assert k.previous_high(changed, 2)[2] == D("15")
    assert k.previous_low(changed, 2)[2] == D("9")
    assert k.previous_high(changed, 2)[3] == D("1000")
    assert k.previous_low(changed, 2)[3] == D("1")


def test_return_positive_negative_flat_warmup_and_observed_lookback() -> None:
    values = k.observed_closes(bars(("10", "12", "9", "9")))
    assert k.trailing_return(values, 1) == (None, D("0.2"), D("-0.25"), D("0"))
    assert k.trailing_return(values, 2) == (None, None, D("-0.1"), D("-0.25"))
    assert k.trailing_return(values, 9) == (None,) * 4


def test_explicit_nonterminating_decimal_rounding() -> None:
    assert k.sma((D(1), D(1), D(2)), 3)[2] == D("1." + "3" * 33)
    assert k.trailing_return((D(3), D(4)), 1)[1] == D("0." + "3" * 34)
    assert k.wilder_atr(ranges_fixture(), 3) == (None, None, D(5), D("4." + "6" * 32 + "7"))


@pytest.mark.parametrize(
    "name", ["sma", "ema", "trailing_return", "wilder_atr", "previous_high", "previous_low"]
)
@pytest.mark.parametrize("period", [0, -1, True, 1.5, "2", None])
def test_invalid_periods_rejected(name: str, period: object) -> None:
    values = k.observed_closes(bars()) if name in {"sma", "ema", "trailing_return"} else bars()
    with pytest.raises(ValueError, match="POSITIVE_INTEGER_PERIOD_REQUIRED"):
        getattr(k, name)(values, period)


@pytest.mark.parametrize("name", ["sma", "ema", "trailing_return"])
@pytest.mark.parametrize("value", [0.1, "1", 1, None, D("NaN"), D("Infinity")])
def test_malformed_scalar_input_is_not_silently_skipped(name: str, value: object) -> None:
    with pytest.raises(ValueError):
        getattr(k, name)((D(1), value), 9)


@pytest.mark.parametrize("value", [D(0), D(-1)])
def test_return_requires_positive_closes(value: Decimal) -> None:
    with pytest.raises(ValueError):
        k.trailing_return((D(1), value), 1)


def test_empty_inputs_and_flat_ranges() -> None:
    assert all(column == () for column in columns(()))
    assert k.sma((), 1) == k.ema((), 1) == k.trailing_return((), 1) == ()
    assert k.true_range(bars(("10", "10"))) == (D(0), D(0))
    assert k.wilder_atr(bars(("10", "10")), 2) == (None, D(0))


def test_gap_metadata_and_calculations_continue_without_synthetic_rows() -> None:
    ordinary = bars()
    gapped = bars(offsets=(0, 1, 5, 6))
    metadata = k.gap_metadata(gapped)
    assert [item.preceded_by_gap for item in metadata] == [False, False, True, False]
    assert [item.elapsed_clock_hours for item in metadata] == [None, 1, 4, 1]
    assert [item.gap_duration_hours for item in metadata] == [0, 0, 4, 0]
    assert [item.missing_clock_hours for item in metadata] == [0, 0, 3, 0]
    for index, (normal, with_gap) in enumerate(
        zip(columns(ordinary), columns(gapped), strict=True)
    ):
        assert len(with_gap) == len(gapped)
        if index != 7:
            assert normal == with_gap
    with pytest.raises(FrozenInstanceError):
        metadata[2].preceded_by_gap = False  # type: ignore[misc]


@pytest.mark.parametrize(
    "fast,slow,expected",
    [
        (D(2), D(1), "BULLISH"),
        (D(1), D(2), "BEARISH"),
        (D(1), D(1), "NEUTRAL"),
        (None, D(1), "UNAVAILABLE"),
        (D(1), None, "UNAVAILABLE"),
        (None, None, "UNAVAILABLE"),
    ],
)
def test_moving_average_states(fast: Decimal | None, slow: Decimal | None, expected: str) -> None:
    assert k.moving_average_state(fast, slow).value == expected


@pytest.mark.parametrize(
    "value,high,low,expected",
    [
        (D(11), D(10), D(5), "UPSIDE_BREAKOUT"),
        (D(4), D(10), D(5), "DOWNSIDE_BREAKOUT"),
        (D(7), D(10), D(5), "INSIDE"),
        (D(10), D(10), D(5), "INSIDE"),
        (D(5), D(10), D(5), "INSIDE"),
        (D(5), D(5), D(5), "INSIDE"),
        (None, D(10), D(5), "UNAVAILABLE"),
        (D(7), None, D(5), "UNAVAILABLE"),
        (D(7), D(10), None, "UNAVAILABLE"),
        (None, None, None, "UNAVAILABLE"),
    ],
)
def test_channel_states(
    value: Decimal | None, high: Decimal | None, low: Decimal | None, expected: str
) -> None:
    assert k.channel_breakout_state(value, high, low).value == expected


@pytest.mark.parametrize(
    "value,expected",
    [(D(1), "POSITIVE"), (D(-1), "NEGATIVE"), (D(0), "FLAT"), (None, "UNAVAILABLE")],
)
def test_momentum_states(value: Decimal | None, expected: str) -> None:
    assert k.momentum_state(value).value == expected


def test_classifications_reject_malformed_and_reversed_channel() -> None:
    with pytest.raises(ValueError):
        k.moving_average_state(D("NaN"), None)
    with pytest.raises(ValueError):
        k.channel_breakout_state(D(1), D(1), D(2))
    with pytest.raises(ValueError):
        k.momentum_state(0.1)  # type: ignore[arg-type]


def test_no_lookahead_prefix_and_future_mutation_for_every_output() -> None:
    observations = ranges_fixture()
    full = columns(observations)
    for length in range(1, len(observations) + 1):
        assert tuple(column[:length] for column in full) == columns(observations[:length])
    for index in range(1, len(observations)):
        mutated = observations[:index] + tuple(
            bar.model_copy(update={"open": D(100), "high": D(101), "low": D(99), "close": D(100)})
            for bar in observations[index:]
        )
        assert tuple(column[:index] for column in full) == tuple(
            column[:index] for column in columns(mutated)
        )


def test_repeat_bytes_context_isolation_and_no_input_mutation() -> None:
    observations = ranges_fixture()
    before = tuple(bar.model_dump_json() for bar in observations)

    def encoded() -> bytes:
        values = columns(observations)
        return canonical_bytes(
            {
                "values": values[:7] + values[8:],
                "gaps": [asdict(item) for item in k.gap_metadata(observations)],
            }
        )

    expected = encoded()
    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        context.Emax = 1
        context.Emin = -1
        assert encoded() == expected
        assert context.prec == 3 and context.rounding == ROUND_DOWN and context.traps[Inexact]
        assert context.Emax == 1 and context.Emin == -1
    assert encoded() == expected
    assert tuple(bar.model_dump_json() for bar in observations) == before


@pytest.mark.parametrize(
    "name",
    [
        "observed_closes",
        "gap_metadata",
        "true_range",
        "wilder_atr",
        "previous_high",
        "previous_low",
    ],
)
@pytest.mark.parametrize(
    "problem",
    [
        "duplicate",
        "reversed",
        "dataset",
        "asset",
        "metadata",
        "ohlc",
        "naive",
        "offset",
        "alignment",
        "raw",
    ],
)
def test_normalized_chronological_contract_required(name: str, problem: str) -> None:
    first, second = bars()[:2]
    changes: dict[str, object] = {
        "dataset": {"dataset_id": "different"},
        "asset": {"canonical_asset": Asset.XAUUSD, "broker_symbol": "XAUUSDm"},
        "metadata": {"instrument_metadata_reference": "1" * 64},
        "ohlc": {"high": D(1)},
        "naive": {"open_time": datetime(2024, 1, 1)},
        "offset": {"open_time": datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=7)))},
        "alignment": {"open_time": START + timedelta(minutes=1)},
    }
    observations: object
    if problem == "duplicate":
        observations = (first, first)
    elif problem == "reversed":
        observations = (second, first)
    elif problem == "raw":
        observations = (first.model_dump(),)
    else:
        update = changes[problem]
        assert isinstance(update, dict)
        observations = (first, second.model_copy(update=update))
    args = (
        (observations, 2)
        if name in {"wilder_atr", "previous_high", "previous_low"}
        else (observations,)
    )
    with pytest.raises(ValueError):
        getattr(k, name)(*args)
