"""Asset-local splits and single-series gross price-R summaries."""

from decimal import Decimal
from typing import Any

from trading_ecosystem.backtests.contracts import MetricState, Split, SplitName
from trading_ecosystem.datasets.contracts import Bar
from trading_ecosystem.domain.arithmetic import arithmetic_context


def splits(bars: tuple[Bar, ...]) -> tuple[Split, ...]:
    count = len(bars)
    edges = (0, count * 3 // 5, count * 4 // 5, count)
    if count < 5:
        raise ValueError("AT_LEAST_FIVE_OBSERVATIONS_FOR_SPLITS")
    return tuple(
        Split(
            name=name,
            first_index=edges[index],
            end_index_exclusive=edges[index + 1],
            first_decision_time=bars[edges[index]].close_time,
            last_decision_time=bars[edges[index + 1] - 1].close_time,
        )
        for index, name in enumerate(SplitName)
    )


def split_at(index: int, definitions: tuple[Split, ...]) -> SplitName:
    return next(
        item.name for item in definitions if item.first_index <= index < item.end_index_exclusive
    )


def mean(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal(0)) / len(values) if values else None


def median(values: list[Decimal]) -> Decimal | None:
    ordered = sorted(values)
    size = len(ordered)
    if not size:
        return None
    return ordered[size // 2] if size % 2 else (ordered[size // 2 - 1] + ordered[size // 2]) / 2


def summarize(records: list[dict[str, Any]], eligibility_count: int) -> dict[str, Any]:
    with arithmetic_context():
        completed = [item for item in records if item["status"] == "COMPLETED"]
        filled = [item for item in records if item["entry_time"] is not None]
        values = [Decimal(item["gross_price_R"]) for item in completed]
        positive, negative = [x for x in values if x > 0], [x for x in values if x < 0]
        pos_sum, neg_sum = sum(positive, Decimal(0)), -sum(negative, Decimal(0))
        pf = {
            "state": MetricState.FINITE
            if negative
            else MetricState.POSITIVE_INFINITY
            if positive
            else MetricState.UNDEFINED,
            "value": pos_sum / neg_sum if negative else None,
        }
        winning = losing = max_winning = max_losing = 0
        for value in values:
            winning = winning + 1 if value > 0 else 0
            losing = losing + 1 if value < 0 else 0
            max_winning, max_losing = max(max_winning, winning), max(max_losing, losing)
        ambiguous = sum(bool(item["intrabar_ambiguous"]) for item in completed)
        return {
            "entry_eligibility_count": eligibility_count,
            "entry_intent_count": len(records),
            "filled_entries": len(filled),
            "completed_episodes": len(completed),
            "open_at_boundary_count": sum(
                item["status"] == "OPEN_AT_EVALUATION_BOUNDARY" for item in records
            ),
            "unfilled_intents": len(records) - len(filled),
            "wins": len(positive),
            "losses": len(negative),
            "break_even_episodes": len(values) - len(positive) - len(negative),
            "win_rate": Decimal(len(positive)) / len(values) if values else None,
            "gross_cumulative_R": sum(values, Decimal(0)),
            "mean_gross_R": mean(values),
            "median_gross_R": median(values),
            "average_winning_R": mean(positive),
            "average_losing_R": mean(negative),
            "profit_factor_R": pf,
            "maximum_winning_streak": max_winning,
            "maximum_losing_streak": max_losing,
            "average_holding_observed_bars": mean(
                [Decimal(item["holding_observed_bars"]) for item in completed]
            ),
            "median_holding_observed_bars": median(
                [Decimal(item["holding_observed_bars"]) for item in completed]
            ),
            "average_holding_clock_hours": mean(
                [Decimal(item["holding_clock_hours"]) for item in completed]
            ),
            "intrabar_ambiguous_count": ambiguous,
            "intrabar_ambiguous_rate": Decimal(ambiguous) / len(completed) if completed else None,
            "gap_entry_count": sum(bool(item["gap_entry"]) for item in filled),
            "gap_exit_count": sum(bool(item["gap_exit"]) for item in completed),
            "gap_adjacent_signal_count": sum(
                bool(item["preceded_by_gap_at_signal"]) for item in records
            ),
            "cross_split_episode_count": sum(bool(item["cross_split"]) for item in filled),
        }
