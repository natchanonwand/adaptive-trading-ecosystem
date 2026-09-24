from decimal import Decimal as D
from decimal import InvalidOperation

import pytest

from trading_ecosystem.behavioral_research.contracts import ResearchConfig, canonical
from trading_ecosystem.behavioral_research.statistics import (
    association,
    bin_values,
    categories,
    cramers_v,
    median_interval,
    numeric,
    proportion_effect,
    quantile_edges,
    rate,
    tier,
)


def test_known_numeric_distribution_and_missingness() -> None:
    result = numeric(["1", "2", None, "3", "4"])
    assert (result["n"], result["known_count"], result["missing_count"]) == (5, 4, 1)
    assert D(result["mean"]) == D("2.5") and D(result["median"]) == D("2.5")
    assert D(result["p25"]) == D("1.75")


@pytest.mark.parametrize("values", [[], [None], [None, None]])
def test_empty_and_missing_samples_are_not_zero(values: list[object]) -> None:
    result = numeric(values)
    assert result["mean"] is None and result["known_count"] == 0
    assert "NaN" not in canonical(result)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", True])
def test_nonfinite_and_boolean_numbers_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        numeric([value])


def test_wilson_rate_and_null_denominator() -> None:
    value = rate([True] * 5 + [False] * 5 + [None])
    assert value["value"] == "0.5" and value["known_count"] == 10 and value["missing_count"] == 1
    assert abs(D(value["interval"][0]) - D(".236593")) < D(".000001")
    assert rate([None])["interval"] is None
    assert D(rate([True] * 10)["interval"][1]) <= 1
    assert D(rate([False] * 10)["interval"][0]) >= 0


@pytest.mark.parametrize("spearman", [False, True])
def test_numeric_association_known_perfect_and_constant(spearman: bool) -> None:
    good = association([1, 2, 3, None], [3, 2, 1, 0], spearman=spearman)
    assert D(good["value"]) == -1 and good["missing_count"] == 1
    assert association([1, 1, 1], [2, 3, 4], spearman=spearman)["value"] is None
    assert association([1], [2], spearman=spearman)["reason"] == "INSUFFICIENT_SAMPLE"


def test_spearman_ties_and_categorical_association() -> None:
    assert D(association([1, 1, 3], [5, 5, 8])["value"]) == 1
    assert D(cramers_v(["a", "a", "b", "b"], ["x", "x", "y", "y"])["value"]) == 1
    assert D(cramers_v(["a", "a", "b", "b"], ["x", "y", "x", "y"])["value"]) == 0
    assert cramers_v([None], ["x"])["value"] is None
    with pytest.raises(InvalidOperation):
        association(["BUY"] * 3, [1, 2, 3])


def test_quantiles_are_deterministic_deduplicated_right_open() -> None:
    cfg = ResearchConfig()
    edges = quantile_edges([0, 1, 2, 3, 4], cfg)
    assert edges == [D(1), D(2), D(3)]
    assert bin_values([None, 0, 1, 2, 3, 4], edges) == [
        None,
        "bin_0",
        "bin_1",
        "bin_2",
        "bin_3",
        "bin_3",
    ]
    assert quantile_edges([1] * 20, cfg) == [D(1)]


def test_bootstrap_resamples_sessions_and_is_seeded() -> None:
    cfg = ResearchConfig()
    a = median_interval([1, 1, 4, 4], ["a", "a", "b", "b"], cfg)
    assert a == median_interval([1, 1, 4, 4], ["a", "a", "b", "b"], cfg)
    assert a["interval"] == ["1.000", "4.000"] or [D(v) for v in a["interval"]] == [1, 4]
    assert median_interval([1, 2], ["a", "a"], cfg)["interval"] is None


def test_effect_sizes_and_infinite_odds_are_explicit() -> None:
    effect = proportion_effect([True, True, False], [True, False, False])
    assert D(effect["odds_ratio"]) == 4
    zero = proportion_effect([True], [False])
    assert zero["odds_ratio"] is None and zero["odds_reason"] == "ZERO_DENOMINATOR_NO_PSEUDOCOUNT"
    assert proportion_effect([None], [True])["difference"] is None


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "INSUFFICIENT"),
        (29, "INSUFFICIENT"),
        (30, "PRELIMINARY"),
        (100, "USABLE"),
        (300, "STRONGER_EVIDENCE"),
    ],
)
def test_documented_sufficiency_tiers(n: int, expected: str) -> None:
    assert tier(n, ResearchConfig()) == expected


@pytest.mark.parametrize(
    "change",
    [
        dict(usable_n=30),
        dict(rsi_edges=[70, 30]),
        dict(seed=-1),
        dict(candidate_id=""),
        dict(quantile_probabilities=[0, 1]),
    ],
)
def test_config_rejects_invalid_policies(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ResearchConfig.model_validate(change)


def test_categories_keep_unknown_and_explicit_denominators() -> None:
    result = categories(["BUY", "SELL", None])
    assert result["missing_count"] == 1 and result["categories"]["BUY"]["value"] == "0.5"
