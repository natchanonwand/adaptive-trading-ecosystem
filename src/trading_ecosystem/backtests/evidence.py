"""Exclusive local evidence writes, independent reload verification and factual reporting."""

import json
from pathlib import Path
from typing import Any

from trading_ecosystem.backtests.metrics import summarize
from trading_ecosystem.benchmarks.contracts import BenchmarkId
from trading_ecosystem.benchmarks.hashing import benchmark_definition_sha256, registry_sha256
from trading_ecosystem.benchmarks.registry import get_definition
from trading_ecosystem.simulation.contracts import SimulationResult
from trading_ecosystem.simulation.hashing import canonical_value, digest


def encoded(value: object) -> bytes:
    return (
        json.dumps(
            canonical_value(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def verify_result(result: dict[str, Any]) -> None:
    content = {key: value for key, value in result.items() if key != "result_sha256"}
    if result["result_sha256"] != digest(content):
        raise ValueError("RESEARCH_RESULT_HASH_MISMATCH")
    definition = get_definition(BenchmarkId(result["benchmark_id"]))
    if (
        result["benchmark_definition_hash"] != benchmark_definition_sha256(definition)
        or result["registry_sha256"] != registry_sha256()
    ):
        raise ValueError("FROZEN_REGISTRY_MISMATCH")
    if (
        result["qualification_eligible"] is not False
        or result["research_classification"] != "EXPLORATORY_RESEARCH_ONLY"
    ):
        raise ValueError("RESEARCH_CLASSIFICATION_MISMATCH")
    records = result["records"]
    last_end = -1
    for record in records:
        if record["signal_index"] <= last_end:
            raise ValueError("OVERLAPPING_OR_SAME_BAR_REENTRY")
        last_end = record["signal_index"]
        if "simulation_result" in record:
            simulation = SimulationResult.model_validate(record["simulation_result"])
            if record["entry_time"] is not None:
                last_end += max(event.bar_index for event in simulation.events)
            if simulation.status.value != record["status"]:
                raise ValueError("EPISODE_STATUS_MISMATCH")
            if simulation.episode:
                if str(simulation.episode.gross_price_R) != record["gross_price_R"]:
                    raise ValueError("EPISODE_R_MISMATCH")
                if simulation.episode.exit.intrabar_ambiguous != record["intrabar_ambiguous"]:
                    raise ValueError("AMBIGUITY_MISMATCH")
    expected = canonical_value(summarize(records, result["metrics"]["entry_eligibility_count"]))
    if result["metrics"] != expected:
        raise ValueError("RESEARCH_METRICS_MISMATCH")
    for name, metrics in result["split_metrics"].items():
        expected = canonical_value(
            summarize(
                [record for record in records if record["split"] == name],
                metrics["entry_eligibility_count"],
            )
        )
        if metrics != expected:
            raise ValueError("SPLIT_METRICS_MISMATCH")


def reload_result(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(path.read_bytes())
    verify_result(result)
    if path.read_bytes() != encoded(result):
        raise ValueError("NONCANONICAL_RESEARCH_EVIDENCE")
    return result


def persist(path: Path, result: dict[str, Any]) -> None:
    verify_result(result)
    if path.exists():
        if reload_result(path) != result:
            raise ValueError("EXISTING_VERIFIED_RESULT_CONFLICT")
        return
    partial = path.with_suffix(".partial")
    data = encoded(result)
    if partial.exists():
        if partial.read_bytes() != data:
            raise ValueError("PARTIAL_EVIDENCE_CONFLICT_PRESERVED")
    else:
        with partial.open("xb") as stream:
            stream.write(data)
    reload_result(partial)
    with path.open("xb") as stream:
        stream.write(data)
    reload_result(path)


def display(value: object) -> str:
    if value is None:
        return "undefined"
    return str(value)


def report_text(run_id: str, results: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 3.3B single-asset exploratory research",
        "",
        "Baseline: `phase3.3a-v0.1.0`. Research run: `" + run_id + "`.",
        (
            "EXPLORATORY_RESEARCH_ONLY; qualification_eligible=false. NO PARAMETER "
            "SELECTION WAS PERFORMED."
        ),
        "",
        "Registry SHA-256: `"
        + registry_sha256()
        + "` <!-- pragma: allowlist secret -- verified SHA-256 -->",
        "",
        "Execution model: exploratory-ohlc-v0.1.0. Cost model: COST_MODEL_BASELINE_V0.",
        (
            "Spread is UNMODELED: current metadata and bar spread fields do not "
            "establish historically available opening spread. Mechanical spread "
            "inputs are zero placeholders, not observed zero costs. Slippage, "
            "commission and financing are explicitly zero. Frozen current-snapshot "
            "trade_tick_size is an exploratory increment assumption. Gross R "
            "excludes additional exit/cash costs; no monetary net R is calculated."
        ),
        "",
        "## Dataset identities and split boundaries",
    ]
    for result in results[::4]:
        lines += ["", "### " + result["asset"]]
        for field in (
            "dataset_id",
            "dataset_manifest_hash",
            "manifest_file_sha256",
            "parquet_sha256",
            "metadata_sha256",
        ):
            lines.append(
                "- "
                + field
                + ": `"
                + result[field]
                + "` <!-- pragma: allowlist secret -- verified SHA-256 -->"
            )
        lines.append("- Tick increment assumption: " + result["tick_size"])
        lines += [
            "",
            "| Split | Observed index interval | First decision UTC | Last decision UTC |",
            "|---|---|---|---|",
        ]
        for split in result["splits"]:
            lines.append(
                f"| {split['name']} | [{split['first_index']}, {split['end_index_exclusive']}) "
                f"| {split['first_decision_time']} | {split['last_decision_time']} |"
            )
    lines += [
        "",
        (
            "Split sizes use floor(0.6N), floor(0.8N), N. Assignment uses the "
            "observed signal bar whose close is ENTRY DECISION TIME. An episode "
            "stays in that split even when it exits later; boundary crossings are "
            "counted once. Indicators continue across splits and gaps without "
            "filling or resets. No outcomes are used to tune or select parameters."
        ),
        "",
        "## Factual metrics",
    ]
    columns = [
        "entry_eligibility_count",
        "entry_intent_count",
        "filled_entries",
        "completed_episodes",
        "open_at_boundary_count",
        "wins",
        "losses",
        "break_even_episodes",
        "win_rate",
        "gross_cumulative_R",
        "mean_gross_R",
        "median_gross_R",
        "average_winning_R",
        "average_losing_R",
        "maximum_winning_streak",
        "maximum_losing_streak",
        "average_holding_observed_bars",
        "median_holding_observed_bars",
        "average_holding_clock_hours",
        "intrabar_ambiguous_count",
        "intrabar_ambiguous_rate",
        "gap_entry_count",
        "gap_exit_count",
        "gap_adjacent_signal_count",
        "cross_split_episode_count",
    ]
    # Vertical per-series columns keep the full mandatory metrics readable.
    for offset in range(0, 12, 4):
        group = results[offset : offset + 4]
        lines += [
            "",
            "### " + group[0]["asset"],
            "",
            "| Metric | B01 | B02 | B03 | B04 |",
            "|---|---:|---:|---:|---:|",
        ]
        for field in columns:
            lines.append(
                "| "
                + field
                + " | "
                + " | ".join(display(item["metrics"][field]) for item in group)
                + " |"
            )
        lines.append(
            "| profit_factor_R | "
            + " | ".join(
                display(item["metrics"]["profit_factor_R"]["value"])
                if item["metrics"]["profit_factor_R"]["state"] == "FINITE"
                else item["metrics"]["profit_factor_R"]["state"]
                for item in group
            )
            + " |"
        )
    lines += [
        "",
        "## Split R metrics",
        "",
        (
            "| Asset | Benchmark | Split | Completed | Wins | Losses | Break-even |"
            " Win rate | Sum R | Mean R | Median R | Avg win R | Avg loss R | PF "
            "state/value |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for result in results:
        for name, metrics in result["split_metrics"].items():
            fields = [
                "completed_episodes",
                "wins",
                "losses",
                "break_even_episodes",
                "win_rate",
                "gross_cumulative_R",
                "mean_gross_R",
                "median_gross_R",
                "average_winning_R",
                "average_losing_R",
            ]
            pf = metrics["profit_factor_R"]
            lines.append(
                "| "
                + result["asset"]
                + " | "
                + result["benchmark_id"]
                + " | "
                + name
                + " | "
                + " | ".join(display(metrics[field]) for field in fields)
                + " | "
                + pf["state"]
                + "/"
                + display(pf["value"])
                + " |"
            )
    lines += [
        "",
        "## Boundary positions",
        "",
        (
            "| Asset | Benchmark | Signal UTC | Entry UTC | Entry fill | Fixed stop"
            " | Target | Split | Cross split |"
        ),
        "|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for result in results:
        for item in result["records"]:
            if item["status"] == "OPEN_AT_EVALUATION_BOUNDARY":
                lines.append(
                    "| "
                    + " | ".join(
                        display(item[field])
                        for field in [
                            "asset",
                            "benchmark_id",
                            "signal_time",
                            "entry_time",
                            "entry_fill",
                            "fixed_stop",
                            "take_profit",
                            "split",
                            "cross_split",
                        ]
                    )
                    + " |"
                )
    lines += ["", "## Result identities", ""]
    for result in results:
        lines.append(
            "- "
            + result["asset"]
            + " / "
            + result["benchmark_id"]
            + ": `"
            + result["result_sha256"]
            + "` <!-- pragma: allowlist secret -- verified SHA-256 -->"
        )
    lines += [
        "",
        "## Diagnostics, denominators and limitations",
        "",
        (
            "Ambiguity rate uses completed episodes as denominator; gap entries "
            "count filled episodes; gap exits count completed episodes; gap-"
            "adjacent signals count accepted intents. All eligibility, including "
            "signals suppressed while occupied, is reported separately. Streaks "
            "follow completed episode order, with break-even breaking both streaks."
            " Holding observed bars counts entry through exit/boundary inclusively;"
            " clock hours use modeled timestamps. Means and R ratios use Decimal34 "
            "half-even. Undefined metrics remain null; profit factor is "
            "POSITIVE_INFINITY only with positive R and no negative R, otherwise "
            "UNDEFINED when both sums are zero."
        ),
        (
            "No same-bar reentry: after any exit the next eligible signal must be "
            "on a later observed bar. Open boundary episodes are never flattened or"
            " included in completed-episode R metrics. Split metrics own the whole "
            "episode by its signal decision; later-split outcomes for cross-split "
            "episodes are disclosed rather than censored or duplicated. Locked OOS "
            "is a chronological label, not an untouched external experiment after "
            "this authorized run."
        ),
        (
            "Price basis remains MT5_CHART_BAR_BASIS_UNVERIFIED; availability "
            "remains MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH; instrument "
            "metadata scope remains CURRENT_SNAPSHOT_ONLY. Gaps are unclassified. "
            "Unknown intrabar chronology assumes stop first; opening target gaps "
            "receive no favorable improvement. Modeled microsecond timing is "
            "ordering, not observed latency. Costs and historical tick validity are"
            " unresolved; gross price R is not cash performance or evidence of "
            "validated edge, execution fidelity, production readiness or "
            "qualification."
        ),
        (
            "All results are independent asset × benchmark series. No portfolio "
            "metrics, parameter selection, optimization, benchmark promotion or "
            "Phase 3.3C work was performed. Generated JSON and retained partial "
            "files are Git-ignored; canonical identities exclude machine paths and "
            "generation times."
        ),
        "",
    ]
    return "\n".join(lines)
