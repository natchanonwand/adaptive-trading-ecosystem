"""Prespecified descriptive analyses. Entry samples cannot estimate entry opportunity rates."""

from collections.abc import Sequence
from decimal import Decimal

from trading_ecosystem.behavioral_research.contracts import Record, ResearchConfig
from trading_ecosystem.behavioral_research.loader import ResearchDataset
from trading_ecosystem.behavioral_research.statistics import (
    association,
    bin_values,
    categories,
    counts,
    cramers_v,
    median_interval,
    number,
    numeric,
    proportion_effect,
    quantile_edges,
    rate,
    tier,
)
from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.features.registry import CATALOG


def values(rows: list[Record], name: str) -> list[object]:
    return [r.get(name) for r in rows]


def numeric_fields(rows: list[Record], names: tuple[str, ...]) -> Record:
    return {name: numeric(values(rows, name)) for name in names}


def flag(value: object, threshold: Decimal = Decimal(0)) -> bool | None:
    parsed = number(value)
    return None if parsed is None else parsed > threshold


def division(a: object, b: object) -> str | None:
    x, y = number(a), number(b)
    return str(x / y) if x is not None and y is not None and y > 0 else None


def conditional(labels: Sequence[object], outcomes: list[bool | None]) -> Record:
    if len(labels) != len(outcomes):
        raise ValueError("UNPAIRED_CONDITIONAL_SAMPLE")
    return dict(
        **counts(len(labels), sum(v is not None for v in labels)),
        condition_distribution=categories(labels),
        groups={
            str(label): rate(
                [
                    v
                    for k, v in zip(labels, outcomes, strict=True)
                    if k is not None and str(k) == label
                ]
            )
            for label in sorted({str(v) for v in labels if v is not None})
        },
        population="OBSERVED_EPISODE_ENTRIES_ONLY",
    )


def temporal(rows: list[Record], ys: dict[tuple[str, str], Record], field: str) -> Record:
    result = categories(values(rows, field))
    result["groups"] = {}
    for label in result["categories"]:
        subset = [r for r in rows if r.get(field) is not None and str(r[field]) == label]
        result["groups"][label] = dict(
            **counts(len(subset), len(subset)),
            direction=categories(values(subset, "direction")),
            volume=numeric(values(subset, "entry_volume")),
            holding_duration=numeric(
                [ys[(r["session_id"], r["episode_id"])]["holding_duration"] for r in subset]
            ),
        )
    return result


def analyze(dataset: ResearchDataset, config: ResearchConfig) -> Record:
    with arithmetic_context():
        return _analyze(dataset, config)


def _analyze(dataset: ResearchDataset, config: ResearchConfig) -> Record:
    xs, entries, outcomes = dataset.episodes, dataset.entries, dataset.outcomes
    ys = {(r["session_id"], r["episode_id"]): r for r in outcomes}
    paired = [ys[(r["session_id"], r["episode_id"])] for r in xs]
    buy = [None if r["direction"] not in ("BUY", "SELL") else r["direction"] == "BUY" for r in xs]
    sell = [None if v is None else not v for v in buy]
    result: Record = dict(
        sample=dict(
            **counts(len(xs), len(xs)),
            entry_fills=len(entries),
            sessions=len({r["session_id"] for r in xs}),
            candidates=categories(values(xs, "candidate_id")),
            source_confidence=categories(values(xs, "source_confidence")),
            entry_time_known=rate([r["entry_time_known"] for r in xs]),
            sufficiency=tier(len(xs), config),
        ),
        direction=dict(buy=rate(buy), sell=rate(sell), symbols=categories(values(xs, "symbol"))),
        temporal={
            field: temporal(xs, ys, field) for field in ("hour_utc", "day_of_week", "session")
        },
        direction_by_symbol=conditional(values(xs, "symbol"), buy),
        direction_by_session=conditional(values(xs, "session"), buy),
        volume=numeric_fields(
            xs,
            (
                "entry_volume",
                "previous_entry_volume",
                "volume_ratio_vs_previous",
                "same_direction_sequence_length",
                "same_symbol_open_count",
                "same_direction_open_count",
                "entry_account_equity",
            ),
        ),
        entry_fill_volume=numeric_fields(entries, ("entry_volume", "volume_ratio_vs_previous")),
        stops=numeric_fields(
            xs,
            (
                "initial_SL_distance",
                "initial_TP_distance",
                "m15_stop_distance_atr",
                "m15_tp_distance_atr",
                "reward_to_risk_observed",
            ),
        ),
        outcomes=numeric_fields(
            paired,
            tuple(d.name for d in CATALOG if not d.causal and d.dtype in ("decimal", "integer")),
        ),
        spacing=numeric_fields(
            xs, ("time_since_previous_entry", "price_distance_from_previous_entry")
        ),
        spread=numeric_fields(
            xs,
            (
                "entry_spread_absolute",
                "entry_spread_points",
                "entry_spread_ticks",
                "entry_spread_bps",
            ),
        ),
    )
    result["stops"].update({field: rate([r[field] for r in xs]) for field in ("has_SL", "has_TP")})
    result["stop_changes"] = {
        field: rate([flag(r[field]) for r in paired])
        for field in ("SL_change_count", "TP_change_count", "SL_removed_count", "TP_removed_count")
    }
    result["volume"]["increase_fraction"] = rate(
        [flag(r["volume_ratio_vs_previous"], Decimal(1)) for r in xs]
    )
    prior_volume_edges = quantile_edges(values(xs, "previous_entry_volume"), config)
    result["volume"]["increase_by_prior_volume"] = conditional(
        bin_values(values(xs, "previous_entry_volume"), prior_volume_edges),
        [flag(r["volume_ratio_vs_previous"], Decimal(1)) for r in xs],
    )
    result["volume"]["prior_volume_bins"] = dict(
        edges=[str(v) for v in prior_volume_edges],
        closed="LEFT",
        method="TYPE7_QUANTILE_DEDUPLICATED",
        fit_population="SELECTED_EPISODES_DESCRIPTIVE_ONLY",
    )
    result["volume"]["scale_in_fraction"] = rate([flag(r["increase_count"]) for r in paired])
    result["volume"]["holding_median_interval"] = median_interval(
        values(paired, "holding_duration"), [r["session_id"] for r in xs], config
    )
    result["volume"]["entry_median_interval"] = median_interval(
        values(xs, "entry_volume"), [r["session_id"] for r in xs], config
    )
    spacing_atr = [
        division(
            abs(v) if (v := number(r["price_distance_from_previous_entry"])) is not None else None,
            r["m15_atr14"],
        )
        for r in xs
    ]
    result["spacing"]["absolute_price_distance_in_entry_atr"] = numeric(spacing_atr)
    same = [
        r
        for r in xs
        if r.get("previous_episode_direction") == r["direction"]
        and r.get("candidate_id") is not None
    ]
    result["spacing"]["same_direction"] = numeric_fields(
        same, ("time_since_previous_entry", "price_distance_from_previous_entry")
    )
    result["spacing"]["same_direction"]["eligibility"] = counts(len(xs), len(same))
    result["spacing"]["basis"] = "PRIOR_KNOWN_CANDIDATE_SAME_SYMBOL_FEATURES"
    ratios, regularity, reset = [], [], []
    for row in paired:
        sequence = [number(v) for v in row["entry_volume_sequence"]]
        known_sequence = [v for v in sequence if v is not None]
        rs = [b / a for a, b in zip(known_sequence, known_sequence[1:], strict=False) if a > 0]
        ratios.extend(rs)
        reset.append(
            None
            if len(known_sequence) < 3
            else any(
                c <= known_sequence[0] and b > known_sequence[0]
                for b, c in zip(known_sequence[1:], known_sequence[2:], strict=False)
            )
        )
        prices = [number(v) for v in row["entry_price_sequence"]]
        clean_prices = [v for v in prices if v is not None]
        gaps = [abs(b - a) for a, b in zip(clean_prices, clean_prices[1:], strict=False)]
        summary = numeric(list(gaps))
        regularity.append(division(summary["std"], summary["mean"]) if len(gaps) >= 2 else None)
    result["volume"]["within_episode_successive_ratios"] = numeric(list(ratios))
    result["volume"]["within_episode_observed_reset"] = rate(reset)
    result["spacing"]["within_episode_spacing_cv"] = numeric(regularity)
    result["spacing"]["basket_close"] = dict(
        **counts(len(xs), 0), value=None, reason="NO_CAUSAL_BASKET_ID_IN_PHASE4C"
    )

    market: Record = {}
    for field in (
        "h1_ema20_distance_atr",
        "h1_ema50_distance_atr",
        "h1_ema200_distance_atr",
        "h1_ema20_minus_ema50",
        "h1_ema50_minus_ema200",
        "h1_return_1",
        "m15_return_1",
    ):
        measurements = values(xs, field)
        signs = [
            None
            if (v := number(x)) is None
            else "positive"
            if v > 0
            else "negative"
            if v < 0
            else "zero"
            for x in measurements
        ]
        agreement = [
            None
            if sign in (None, "zero") or direction is None
            else direction == (sign == "positive")
            for sign, direction in zip(signs, buy, strict=True)
        ]
        market[field] = dict(
            summary=numeric(measurements),
            by_sign=conditional(signs, buy),
            direction_agreement=rate(agreement),
        )
    bin_definitions: Record = {}
    for field in (
        "m15_rsi14",
        "h1_rsi14",
        "m15_atr14",
        "h1_atr14",
        "h4_atr14",
        "m15_range_position_20",
    ):
        measurements = values(xs, field)
        edges = list(config.rsi_edges) if "rsi" in field else quantile_edges(measurements, config)
        labels = bin_values(measurements, edges)
        bin_definitions[field] = dict(
            edges=[str(v) for v in edges],
            closed="LEFT",
            outside="UNBOUNDED",
            fit_population="SELECTED_EPISODES_DESCRIPTIVE_ONLY",
            method="FIXED_DOMAIN" if "rsi" in field else "TYPE7_QUANTILE_DEDUPLICATED",
        )
        market[field] = dict(summary=numeric(measurements), bins=conditional(labels, buy))
    result["market_context"], result["bin_definitions"] = market, bin_definitions
    result["entry_opportunity_probability"] = dict(
        **counts(len(xs), 0),
        value=None,
        reason="P_ENTRY_GIVEN_CONTEXT_UNIDENTIFIABLE_WITHOUT_NON_ENTRY_OPPORTUNITIES",
    )
    result["associations"] = dict(
        volume_vs_previous=association(
            values(xs, "previous_entry_volume"), values(xs, "entry_volume")
        ),
        sl_vs_atr=association(values(xs, "initial_SL_distance"), values(xs, "m15_atr14")),
        tp_vs_atr=association(values(xs, "initial_TP_distance"), values(xs, "m15_atr14")),
        direction_session=cramers_v(values(xs, "direction"), values(xs, "session")),
    )
    # Retrospective outcome strata never enter the causal feature tables.
    outcome_labels = [
        None
        if (p := number(r["net_observed_pnl"])) is None
        else "WIN"
        if p > 0
        else "LOSS"
        if p < 0
        else "FLAT"
        for r in paired
    ]
    result["retrospective_outcomes"] = conditional(outcome_labels, buy)
    result["retrospective_outcomes"]["volume_by_outcome"] = {
        label: numeric(
            [
                r["entry_volume"]
                for r, group in zip(xs, outcome_labels, strict=True)
                if group == label
            ]
        )
        for label in ("WIN", "LOSS", "FLAT")
    }
    wins = [b for label, b in zip(outcome_labels, buy, strict=True) if label == "WIN"]
    losses = [b for label, b in zip(outcome_labels, buy, strict=True) if label == "LOSS"]
    result["retrospective_outcomes"]["buy_rate_effect_win_minus_loss"] = proportion_effect(
        wins, losses
    )
    result["prior_adverse_progression"] = prior_adverse(xs, ys)
    return result


def prior_adverse(xs: list[Record], ys: dict[tuple[str, str], Record]) -> Record:
    """Pair earlier available outcomes within the same candidate/symbol/session."""
    from trading_ecosystem.domain.primitives import utc_timestamp

    prior: dict[tuple[str, str, str], Record | None] = {}
    last_at: dict[tuple[str, str, str], str] = {}
    labels: list[object] = []
    increased: list[bool | None] = []
    scale_in: list[bool | None] = []
    for row in sorted(xs, key=lambda r: (r["prediction_cutoff"], r["row_id"])):
        label = None
        increase = None
        key = (row["session_id"], row["candidate_id"], row["symbol"])
        previous = prior.get(key) if row["candidate_id"] is not None else None
        if (
            previous is not None
            and row["entry_time_known"] is True
            and previous["entry_time_known"] is True
            and row["source_confidence"] == previous["source_confidence"] == "KNOWN"
            and utc_timestamp(previous["prediction_cutoff"])
            < utc_timestamp(row["prediction_cutoff"])
        ):
            outcome = ys[(previous["session_id"], previous["episode_id"])]
            pnl = number(outcome["net_observed_pnl"])
            if pnl is not None and utc_timestamp(outcome["available_at"]) <= utc_timestamp(
                row["prediction_cutoff"]
            ):
                label = "PRIOR_LOSS" if pnl < 0 else "PRIOR_NONLOSS"
                increase = flag(division(row["entry_volume"], previous["entry_volume"]), Decimal(1))
        labels.append(label)
        increased.append(increase)
        scale_in.append(flag(ys[(row["session_id"], row["episode_id"])]["increase_count"]))
        if row["candidate_id"] is not None:
            # A tied prior timestamp has no unique preceding episode; do not pick by row ID.
            prior[key] = None if last_at.get(key) == row["prediction_cutoff"] else row
            last_at[key] = row["prediction_cutoff"]
    return dict(
        volume_increase=conditional(labels, increased),
        scale_in=conditional(labels, scale_in),
        limitation="SOURCE_END_OUTCOME_AVAILABILITY_OFTEN_PREVENTS_CAUSAL_PRIOR_LOSS_PAIRING",
    )
