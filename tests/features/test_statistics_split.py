from datetime import timedelta
from decimal import Decimal

from tests.observer.fixtures import T
from trading_ecosystem.features.registry import CATALOG
from trading_ecosystem.features.splits import split
from trading_ecosystem.features.statistics import correlation, describe
from trading_ecosystem.mt5.client import Record


def test_descriptive_missingness_and_population_statistics() -> None:
    rows: list[Record] = [{d.name: None for d in CATALOG if d.causal} for _ in range(3)]
    rows[0]["h1_ema20"] = "1"
    rows[1]["h1_ema20"] = "3"
    result = describe(rows, causal=True)["h1_ema20"]
    assert result["count"] == 2 and result["missing_count"] == 1
    assert result["mean"] == "2" and result["std"] == "1"
    assert result["p25"] == "1.50"


def test_correlations_pairwise_missing_ties_constant_and_small_sample() -> None:
    pairs: list[tuple[Decimal | None, Decimal | None]] = [
        (Decimal(i), Decimal(i * 2)) for i in range(1, 5)
    ]
    pairs.append((None, Decimal(1)))
    assert correlation(pairs)["value"] == "1"
    assert correlation(pairs, spearman=True)["value"] == "1"
    assert correlation([(Decimal(1), Decimal(i)) for i in range(4)])["reason"] == "CONSTANT_COLUMN"
    assert correlation(pairs[:2])["reason"] == "INSUFFICIENT_SAMPLE"
    assert (
        correlation([(Decimal(i), Decimal(i)) for i in (1, 1, 2, 3)], spearman=True)["value"] == "1"
    )


def test_grouped_split_purges_cross_boundary_and_locks_oos() -> None:
    rows = [
        dict(
            row_id=str(i),
            episode_id=str(i),
            session_id="session",
            sequence_group_id="shared" if i < 2 else "later",
            prediction_cutoff=(T + timedelta(days=i)).isoformat(),
        )
        for i in range(3)
    ]
    outcomes = [
        dict(episode_id=str(i), available_at=(T + timedelta(days=i, hours=1)).isoformat())
        for i in range(3)
    ]
    result = split(rows, outcomes, T + timedelta(hours=12), T + timedelta(days=1, hours=12))
    assert result["assignments"] == {
        "0": "purged_boundary_crossing",
        "1": "purged_boundary_crossing",
        "2": "locked_oos",
    }
    grouped = split(
        rows, outcomes, T + timedelta(hours=12), T + timedelta(days=1, hours=12), group_by="session"
    )
    assert set(grouped["assignments"].values()) == {"purged_boundary_crossing"}
