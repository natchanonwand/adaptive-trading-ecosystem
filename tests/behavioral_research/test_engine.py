import ast
import copy
from decimal import Decimal
from pathlib import Path
from random import Random

import pytest

from tests.behavioral_research.fixtures import dataset
from trading_ecosystem.behavioral_research.analysis import analyze
from trading_ecosystem.behavioral_research.contracts import ResearchConfig, canonical
from trading_ecosystem.behavioral_research.engine import build_result, compare
from trading_ecosystem.behavioral_research.reports import artifacts, markdown, packet


def test_fixed_volume_stops_temporal_and_direction_fixture() -> None:
    result = analyze(dataset(), ResearchConfig())
    assert Decimal(result["volume"]["entry_volume"]["std"]) == 0
    assert Decimal(result["stops"]["initial_SL_distance"]["median"]) == 10
    assert result["direction"]["buy"]["value"] == "0.5"
    assert result["temporal"]["session"]["groups"]["UTC_FIXTURE"]["n"] == 12
    assert result["entry_opportunity_probability"]["value"] is None


def test_progression_spacing_reset_and_no_labels() -> None:
    source = dataset()
    for y in source.outcomes:
        y.update(
            entry_volume_sequence=["1", "2", "4", "1"],
            entry_price_sequence=["100", "110", "120", "130"],
            increase_count=3,
        )
    result = build_result(source, ResearchConfig())
    a = result["fingerprint"]["measurements"]
    assert a["volume"]["within_episode_observed_reset"]["value"] == "1"
    assert Decimal(a["spacing"]["within_episode_spacing_cv"]["median"]) == 0
    assert result["hypotheses"] == []


def test_random_rising_volume_and_positions_do_not_classify() -> None:
    source, rng = dataset(120), Random(7)
    for x, y in zip(source.episodes, source.outcomes, strict=True):
        x.update(
            entry_volume=str(rng.randint(1, 10)),
            same_symbol_open_count=rng.randint(1, 12),
            volume_ratio_vs_previous=str(rng.randint(1, 4)),
        )
        y.update(entry_price_sequence=[str(rng.randint(1, 100)) for _ in range(5)])
    result = build_result(source, ResearchConfig())
    assert result["hypotheses"] == [] and result["status"] == "SOFTWARE_VALIDATION_ONLY"
    assert "classification" not in result


def test_imbalanced_buys_report_association_not_entry_filter() -> None:
    source = dataset(90)
    for x in source.episodes:
        x.update(direction="BUY", h1_ema200_distance_atr="1")
    a = analyze(source, ResearchConfig())
    metric = a["market_context"]["h1_ema200_distance_atr"]["by_sign"]["groups"]["positive"]
    assert metric["value"] == "1" and metric["known_count"] == 90
    assert a["entry_opportunity_probability"]["known_count"] == 0


@pytest.mark.parametrize(
    "field", ["has_SL", "has_TP", "h4_atr14", "entry_account_equity", "entry_volume"]
)
def test_missing_features_and_recovered_episode_not_dropped(field: str) -> None:
    source = dataset()
    for x, y in zip(source.episodes, source.outcomes, strict=True):
        x[field] = None
        x["entry_time_known"] = False
        y["holding_duration"] = None
    result = analyze(source, ResearchConfig())
    assert (
        result["sample"]["n"] == 12
        and result["outcomes"]["holding_duration"]["missing_count"] == 12
    )
    assert "NaN" not in canonical(result) and "Infinity" not in canonical(result)


def test_no_future_outcome_enters_causal_sections() -> None:
    original = dataset()
    changed = copy.deepcopy(original)
    for y in changed.outcomes:
        y.update(net_observed_pnl="999", holding_duration="999", SL_change_count=99)
    a, b = analyze(original, ResearchConfig()), analyze(changed, ResearchConfig())
    for field in ("direction", "temporal", "stops", "spacing", "market_context"):
        if field != "temporal":
            assert a[field] == b[field]
    assert a["retrospective_outcomes"] != b["retrospective_outcomes"]


def test_outcome_availability_gates_prior_loss() -> None:
    source = dataset()
    for y in source.outcomes:
        y["available_at"] = "2099-01-01T00:00:00+00:00"
    a = analyze(source, ResearchConfig())
    assert a["prior_adverse_progression"]["volume_increase"]["known_count"] == 0


def test_prior_loss_pairs_same_episode_volume_and_rejects_tied_predecessors() -> None:
    source = dataset(9)
    # Episode 3 follows episode 0 in the same session; its volume doubles.
    source.episodes[3]["entry_volume"] = "2"
    source.episodes[3]["volume_ratio_vs_previous"] = "0.5"
    result = analyze(source, ResearchConfig())["prior_adverse_progression"]
    metric = result["volume_increase"]["groups"]["PRIOR_LOSS"]
    assert metric["successes"] == 1
    # Two prior episode entries at the same observation time cannot be ordered causally.
    source.episodes[3]["prediction_cutoff"] = source.episodes[0]["prediction_cutoff"]
    changed = analyze(source, ResearchConfig())["prior_adverse_progression"]
    assert changed["volume_increase"]["known_count"] < result["volume_increase"]["known_count"]


def test_comparison_rejects_incompatible_feature_sets() -> None:
    a = build_result(dataset(), ResearchConfig())
    b = copy.deepcopy(a)
    b["feature_set_id"] = "different"
    with pytest.raises(ValueError, match="INCOMPATIBLE"):
        compare(a, b)


def test_real_type_tiny_sample_cannot_support_hypotheses() -> None:
    result = build_result(dataset(real_guard=True), ResearchConfig())
    assert result["status"] == "INSUFFICIENT_DATA"
    assert all(h["status"] == "INSUFFICIENT_DATA" for h in result["hypotheses"])
    assert "INSUFFICIENT DATA" in markdown(result)


@pytest.mark.parametrize(
    "aligned,expected",
    [(True, "SUPPORTED_BY_CURRENT_SAMPLE"), (False, "CONTRADICTED_BY_CURRENT_SAMPLE")],
)
def test_real_guard_algorithm_only_hypothesis_fixture(aligned: bool, expected: str) -> None:
    result = build_result(dataset(360, real_guard=True, aligned=aligned), ResearchConfig())
    assert {h["status"] for h in result["hypotheses"]} == {expected}
    assert all(h["confidence"] == "SAMPLE_SUFFICIENCY_ONLY" for h in result["hypotheses"])


@pytest.mark.parametrize(
    "field,value",
    [("candidate_id", None), ("source_confidence", "UNKNOWN"), ("entry_time_known", False)],
)
def test_ambiguous_or_recovered_real_guard_cannot_support(field: str, value: object) -> None:
    source = dataset(360, real_guard=True)
    source.episodes[0][field] = value
    assert all(
        h["status"] == "INSUFFICIENT_DATA"
        for h in build_result(source, ResearchConfig())["hypotheses"]
    )


def test_synthetic_guard_applies_even_to_large_perfect_fixture() -> None:
    result = build_result(dataset(360), ResearchConfig())
    assert result["hypotheses"] == []
    text = markdown(result)
    assert "SOFTWARE VALIDATION DATA ONLY" in text and "NO REAL EA BEHAVIORAL CONCLUSIONS" in text
    assert packet(result)["status"] == "SOFTWARE_VALIDATION_ONLY"


def test_fingerprint_report_packet_determinism_and_seed_identity() -> None:
    source = dataset()
    one, two = build_result(source, ResearchConfig()), build_result(source, ResearchConfig())
    assert one == two and artifacts(one) == artifacts(two)
    assert one["run_id"] != build_result(source, ResearchConfig(seed=1))["run_id"]
    assert "episodes" not in packet(one) and "raw_rows" not in canonical(packet(one))


def test_comparison_reports_differences_without_winners() -> None:
    a, b = dataset(), dataset()
    for row in b.episodes:
        row.update(entry_volume="3", direction="BUY", has_SL=False)
    result = compare(build_result(a, ResearchConfig()), build_result(b, ResearchConfig()))
    assert Decimal(result["measurements"]["volume.entry_volume"]["left_minus_right"]) == -2
    assert result["ranking"] is None and result["status"] == "SOFTWARE_VALIDATION_ONLY"


def test_empty_selection_stays_insufficient() -> None:
    result = build_result(dataset(0), ResearchConfig())
    assert result["fingerprint"]["n"] == 0
    assert result["fingerprint"]["measurements"]["sample"]["sufficiency"] == "INSUFFICIENT"


def test_offline_scope_no_native_or_external_api_dependencies() -> None:
    forbidden = ("MetaTrader5", "openai", "anthropic", "requests", "httpx", "subprocess", "sklearn")
    for path in Path("src/trading_ecosystem/behavioral_research").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not v.name.startswith(forbidden) for v in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(forbidden)
                assert node.module not in {
                    "trading_ecosystem.observer.runtime",
                    "trading_ecosystem.observer.native",
                }
