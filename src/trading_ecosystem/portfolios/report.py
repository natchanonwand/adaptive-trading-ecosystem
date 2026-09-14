"""Factual report with strictly separate analytical layers."""

from decimal import Decimal
from typing import Any


def show(value: Any) -> str:
    if value is None:
        return "UNAVAILABLE"
    if isinstance(value, dict):
        return str(value["value"]) if value["value"] is not None else value["state"]
    return str(value)


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
        *["| " + " | ".join(show(value) for value in row) + " |" for row in rows],
    ]


def report(run_id: str, outputs: list[dict[str, Any]]) -> str:
    primary, secondary = outputs[::2], outputs[1::2]
    first = primary[0]
    lines = [
        "# Phase 3.3C exploratory portfolio research",
        "",
        "Baseline: phase3.3b-v0.1.0. Input run: " + first["input_run_id"] + ".",
        "Portfolio research run: " + run_id + ".",
        (
            "EXPLORATORY_RESEARCH_ONLY; qualification_eligible=false. NO PARAMETER "
            "SELECTION WAS PERFORMED."
        ),
        "",
        "## SECTION A — PRIMARY R-SPACE PORTFOLIO RESULTS",
        "",
        (
            "Cumulative R is realized episode risk units, not percentage return. No"
            " episode R is rescaled."
        ),
        "Model: " + first["aggregation_model_version"] + ".",
        "Common interval (inclusive decision boundaries): "
        + first["common_interval"]["start"]
        + " through "
        + first["common_interval"]["end"]
        + ".",
        (
            "Cuts use exact UTC microseconds: Development [start,60%); Validation "
            "[60%,80%); Locked OOS [80%,end]. Episode assignment uses ENTRY "
            "DECISION TIME; later exits remain in their entry split."
        ),
        "",
    ]
    lines += table(
        ["Split", "Start UTC", "End UTC"],
        [[name, *times] for name, times in first["calendar_splits"].items()],
    )
    lines += [
        "",
        "Registry: `"
        + first["registry_sha256"]
        + "` <!-- pragma: allowlist secret -- verified SHA-256 -->",
        "",
        "### Input identities",
    ]
    for item in primary:
        for asset, value in zip(
            ["BTCUSD", "XAUUSD", "USTEC100"], item["input_result_hashes"], strict=True
        ):
            lines.append(
                "- "
                + item["portfolio_id"]
                + "/"
                + asset
                + ": `"
                + value
                + "` <!-- pragma: allowlist secret -- verified SHA-256 -->"
            )
    lines += ["", "### Realized R metrics", ""]
    fields = [
        "episodes",
        "wins",
        "losses",
        "break_even",
        "win_rate",
        "total_gross_R",
        "mean_R",
        "median_R",
        "average_winning_R",
        "average_losing_R",
        "profit_factor",
        "maximum_winning_streak",
        "maximum_losing_streak",
        "cross_split_episode_count",
    ]
    lines += table(
        ["Metric", "B01", "B02", "B03", "B04"],
        [[field, *[item["analysis"][field] for item in primary]] for field in fields],
    )
    lines += table(
        [
            "Portfolio",
            "Max realized-R DD",
            "Max DD closed-event duration",
            "Max DD clock hours",
            "Max recovered trough-to-peak hours",
            "Peak R",
            "Final R",
            "Max concurrency / risk units",
        ],
        [
            [
                item["portfolio_id"],
                item["analysis"]["drawdown"]["maximum_drawdown"],
                item["analysis"]["drawdown"]["maximum_duration_events"],
                Decimal(item["analysis"]["drawdown"]["maximum_duration_microseconds"])
                / Decimal(3600000000),
                Decimal(item["analysis"]["drawdown"]["max_recovered_trough_to_peak_microseconds"])
                / Decimal(3600000000)
                if item["analysis"]["drawdown"]["max_recovered_trough_to_peak_microseconds"]
                is not None
                else None,
                item["analysis"]["drawdown"]["peak"],
                item["analysis"]["drawdown"]["final"],
                item["analysis"]["concurrency"]["max_concurrent_episodes"],
            ]
            for item in primary
        ],
    )
    lines += [
        "",
        (
            "REALIZED_EPISODE_R_DRAWDOWN uses only closed episodes. Drawdown spells"
            " run from the last equal/new peak to recovery or the common end (later"
            " retained exits extend the horizon). Event duration counts closed "
            "episodes since that peak; unrecovered spells are censored. Recovery is"
            " trough-to-recovery time for recovered spells only. Duration maxima "
            "may belong to different spells from maximum depth. Split drawdowns use"
            " only that split's owned episodes in exit order, with a zero baseline "
            "at common start."
        ),
        "",
        "### Asset contributions and exclusions",
        "",
    ]
    lines += table(
        [
            "Portfolio",
            "Asset",
            "Episodes",
            "Contribution R",
            "% of positive total R",
            "Pre-common excluded",
        ],
        [
            [
                item["portfolio_id"],
                asset,
                values["episodes"],
                values["R"],
                values["percentage_of_positive_total"],
                item["pre_common_excluded"][asset],
            ]
            for item in primary
            for asset, values in item["analysis"]["contributions"].items()
        ],
    )
    lines += [
        "",
        (
            "Contribution percentages are unavailable when total R <= 0; a negative"
            " asset contribution may be negative when the portfolio total is "
            "positive. Excluded inputs remain unchanged."
        ),
        "",
        "### Common split metrics",
        "",
    ]
    lines += table(
        [
            "Portfolio",
            "Split",
            "Episodes",
            "Wins",
            "Losses",
            "Win rate",
            "Total R",
            "Mean R",
            "PF",
            "Realized R DD",
        ],
        [
            [
                item["portfolio_id"],
                name,
                values["episodes"],
                values["wins"],
                values["losses"],
                values["win_rate"],
                values["total_gross_R"],
                values["mean_R"],
                values["profit_factor"],
                values["drawdown"]["maximum_drawdown"],
            ]
            for item in primary
            for name, values in item["analysis"]["splits"].items()
        ],
    )
    lines += ["", "### Concurrency distributions", ""]
    lines += table(
        ["Portfolio", "Open count", "Post-event observations", "UTC hours"],
        [
            [
                item["portfolio_id"],
                count,
                item["analysis"]["concurrency"]["post_event_count_distribution"][count],
                Decimal(duration) / Decimal(3600000000),
            ]
            for item in primary
            for count, duration in item["analysis"]["concurrency"][
                "time_microseconds_distribution"
            ].items()
        ],
    )
    lines += [
        "",
        (
            "Events sort by UTC timestamp, then BTCUSD/XAUUSD/USTEC100, then "
            "verified event priority, sequence and episode identity. Same-asset "
            "concurrency above one is an integrity failure. Time distributions use "
            "the common interval; event counts are post entry/exit observations, "
            "including zero-duration ties. Initial risk units equal the number of "
            "open episodes, without equity conversion."
        ),
        "",
        "## SECTION B — SYNTHETIC USD 300 / 0.25% EQUITY ILLUSTRATION",
        "",
        "**SYNTHETIC_300USD_RISK025_V0 — NOT BROKER-EXECUTABLE PERFORMANCE**",
        (
            "**SPREAD UNMODELED; COMMISSION UNMODELED/ASSUMED ZERO; SLIPPAGE "
            "ASSUMED ZERO; FINANCING ASSUMED ZERO. NO LOT-SIZE FEASIBILITY HAS BEEN"
            " APPLIED. NO MARGIN MODEL. NO LEVERAGE MODEL.**"
        ),
        (
            "Each accepted entry reserves 0.25% of then-current realized equity. "
            "That cash risk is fixed until exit; gross R times reserved risk is "
            "realized on exit. Admission requires at most three episodes, one per "
            "asset, and total reserved risk <= 0.75% of current equity plus 1e-28 "
            "USD tolerance. A later loss can increase the reserved/equity ratio "
            "without changing existing reservations; only new admissions are gated."
            " Rejected episodes and reasons remain in the synthetic ledger; their "
            "outcomes do not enter synthetic equity. Equal-time entries follow "
            "canonical asset order; entry alone does not change equity."
        ),
        "",
    ]
    lines += table(
        [
            "Portfolio",
            "Starting USD",
            "Ending realized USD",
            "Gross USD P/L",
            "Gross return %",
            "Max realized DD USD",
            "Max realized DD %",
            "Max reserved USD",
            "Max reserved %",
            "Rejections",
            "Wins",
            "Losses",
        ],
        [
            [
                item["portfolio_id"],
                item["analysis"]["starting_equity"],
                item["analysis"]["ending_realized_equity"],
                item["analysis"]["gross_synthetic_pnl"],
                Decimal(item["analysis"]["gross_synthetic_return_fraction"]) * 100,
                item["analysis"]["drawdown"]["maximum_drawdown"],
                Decimal(item["analysis"]["drawdown"]["maximum_drawdown_fraction"]) * 100,
                item["analysis"]["max_reserved_risk_usd"],
                Decimal(item["analysis"]["max_reserved_risk_fraction"]) * 100,
                item["analysis"]["risk_rejections"],
                item["analysis"]["wins"],
                item["analysis"]["losses"],
            ]
            for item in secondary
        ],
    )
    lines += ["", "## Monthly and annual summaries — separate units", ""]
    for label, group, unit in [
        ("PRIMARY R-SPACE", primary, "R"),
        ("SECONDARY SYNTHETIC", secondary, "gross USD P/L"),
    ]:
        lines += ["", "### " + label]
        for period in ("annual", "monthly"):
            keys = sorted({key for item in group for key in item["analysis"][period]})
            lines += ["", period + " " + unit + " (all periods, including negative and zero)", ""]
            lines += table(
                ["UTC period", "B01", "B02", "B03", "B04"],
                [
                    [key, *[item["analysis"][period].get(key, {}).get("total") for item in group]]
                    for key in keys
                ],
            )
            lines += ["", period + " completed episode counts", ""]
            lines += table(
                ["UTC period", "B01", "B02", "B03", "B04"],
                [
                    [
                        key,
                        *[item["analysis"][period].get(key, {}).get("episodes") for item in group],
                    ]
                    for key in keys
                ],
            )
    lines += ["", "## Result identities", ""]
    for item in outputs:
        lines.append(
            "- "
            + item["portfolio_id"]
            + "/"
            + item["layer"]
            + ": `"
            + item["result_sha256"]
            + "` <!-- pragma: allowlist secret -- verified SHA-256 -->"
        )
    lines += [
        "",
        "## Limitations",
        "",
        (
            "All outputs are gross descriptive research. Historical spread, "
            "financing, commissions, tick economics, minimum volume, volume step, "
            "contract size and margin feasibility remain unresolved. USD 300 "
            "executability is not established. Phase 3.3B chart-basis, "
            "availability, current-metadata and stop-first OHLC ambiguity "
            "limitations remain. No mark-to-market losses, broker sizing or forced "
            "boundary exits are introduced. No strategy is selected, promoted, "
            "optimized or qualified; Phase 3.4 is not implemented."
        ),
        "",
    ]
    return "\n".join(lines)
