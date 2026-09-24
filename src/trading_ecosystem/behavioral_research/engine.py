"""Versioned reproducible fingerprint and compact evidence packet."""

from decimal import Decimal
from pathlib import Path

from trading_ecosystem.behavioral_research.analysis import analyze
from trading_ecosystem.behavioral_research.contracts import (
    CHECKPOINT,
    SCHEMA,
    BehaviorFingerprint,
    Record,
    ResearchConfig,
    code_hash,
    identity,
)
from trading_ecosystem.behavioral_research.hypotheses import hypotheses
from trading_ecosystem.behavioral_research.loader import ResearchDataset, load
from trading_ecosystem.domain.arithmetic import arithmetic_context

LIMITATIONS = [
    "Descriptive associations are not hidden EA rules, causal effects or strategy classifications.",
    "Episode entries lack non-entry opportunities; entry probability and filter preference "
    "are unidentifiable.",
    "Unknown values are counted, not zero-filled; recovered entry and first-observed "
    "stop semantics persist.",
    "Phase 4C finite history and UTC windows remain; ADX and civil-session/DST "
    "calendars are deferred.",
    "Pooled symbols have different units; use symbol filters before interpreting "
    "raw-price distances or lots.",
    "Wilson intervals assume independent episodes; dependence is not corrected. Bootstrap "
    "resamples sessions, whose independence is not guaranteed.",
    "Evidence tiers are configurable operational sample counts, not calibrated probabilities "
    "or quality grades.",
    "No hypothesis significance tests or p-values are emitted; FDR testing, clustering "
    "and rule mining are deferred.",
    "Quantile bins fit the selected descriptive sample; they are not training or "
    "out-of-sample estimates.",
    "Basket membership and latent intent are unavailable; no grid or martingale "
    "classification is produced.",
    "Prior-loss evidence uses source-end outcome availability; unavailable causal "
    "pairs stay missing.",
]


def research(path: Path, config: ResearchConfig) -> Record:
    return build_result(load(path, config), config)


def build_result(dataset: ResearchDataset, config: ResearchConfig) -> Record:
    analysis = analyze(dataset, config)
    config_hash = identity(config.model_dump(mode="json"))
    source_hash = code_hash()
    kind = dataset.manifest["dataset_type"]
    if kind not in ("SYNTHETIC_QUALIFICATION", "REAL_DEMO_OBSERVATION"):
        raise ValueError("UNSUPPORTED_RESEARCH_DATASET_TYPE")
    fingerprint = BehaviorFingerprint(
        fingerprint_version="behavior-fingerprint-v1-" + source_hash[:24],
        definition_hash=source_hash,
        research_config_hash=config_hash,
        feature_set_id=dataset.manifest["feature_set_id"],
        dataset_hash=dataset.dataset_hash,
        n=len(dataset.episodes),
        known_count=len(dataset.episodes),
        missing_count=0,
        measurements=analysis,
    ).model_dump(mode="json")
    result: Record = dict(
        schema_version=SCHEMA,
        run_id="research4d-" + identity([dataset.dataset_hash, config_hash, source_hash])[:24],
        dataset_hash=dataset.dataset_hash,
        feature_set_id=dataset.manifest["feature_set_id"],
        dataset_type=kind,
        research_config=config.model_dump(mode="json"),
        research_config_hash=config_hash,
        code_version=source_hash,
        baseline_checkpoint=CHECKPOINT,
        seed=config.seed,
        source_session_ids=dataset.manifest["session_ids"],
        selected_session_ids=sorted({r["session_id"] for r in dataset.episodes}),
        selected_candidates=sorted(
            {r["candidate_id"] for r in dataset.episodes if r["candidate_id"] is not None}
        ),
        selected_symbols=sorted({r["symbol"] for r in dataset.episodes}),
        status="SOFTWARE_VALIDATION_ONLY"
        if kind == "SYNTHETIC_QUALIFICATION"
        else "INSUFFICIENT_DATA"
        if analysis["sample"]["sufficiency"] == "INSUFFICIENT"
        else "DESCRIPTIVE_RESEARCH_ONLY",
        fingerprint=fingerprint,
        hypotheses=hypotheses(dataset, analysis, config),
        limitations=LIMITATIONS,
        real_ea_research_qualification="NOT_PROVIDED"
        if kind == "SYNTHETIC_QUALIFICATION"
        else "NOT_AUTOMATICALLY_QUALIFIED",
        no_external_api_calls=True,
        qualification_eligible=False,
    )
    result["content_hash"] = identity(result)
    return result


def compare(left: Record, right: Record) -> Record:
    if left["feature_set_id"] != right["feature_set_id"]:
        raise ValueError("INCOMPATIBLE_FEATURE_SETS")
    measurements: Record = {}
    a, b = left["fingerprint"]["measurements"], right["fingerprint"]["measurements"]
    paths = (
        ("direction", "buy", "value"),
        ("stops", "has_SL", "value"),
        ("stops", "has_TP", "value"),
        ("volume", "entry_volume", "median"),
        ("outcomes", "holding_duration", "median"),
        ("spacing", "time_since_previous_entry", "median"),
    )
    with arithmetic_context():
        for section, name, field in paths:
            x, y = a[section][name], b[section][name]
            difference = (
                None
                if x[field] is None or y[field] is None
                else str(Decimal(x[field]) - Decimal(y[field]))
            )
            measurements[section + "." + name] = dict(
                left=x, right=y, left_minus_right=difference, statistic=field
            )
    return dict(
        left_run_id=left["run_id"],
        right_run_id=right["run_id"],
        left_dataset_type=left["dataset_type"],
        right_dataset_type=right["dataset_type"],
        status="SOFTWARE_VALIDATION_ONLY"
        if "SYNTHETIC_QUALIFICATION" in (left["dataset_type"], right["dataset_type"])
        else "DESCRIPTIVE_COMPARISON_ONLY",
        measurements=measurements,
        ranking=None,
        limitations=[
            "Descriptive differences, not winners or causal effects.",
            "Check differing symbols, units, periods and selection filters before interpretation.",
        ],
    )
