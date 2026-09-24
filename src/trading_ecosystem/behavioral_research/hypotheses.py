"""Prespecified association hypotheses, real-data gated; never hidden-rule classification."""

from decimal import Decimal

from trading_ecosystem.behavioral_research.contracts import (
    BehaviorHypothesis,
    Record,
    ResearchConfig,
    identity,
)
from trading_ecosystem.behavioral_research.loader import ResearchDataset
from trading_ecosystem.behavioral_research.statistics import number, rate
from trading_ecosystem.domain.arithmetic import arithmetic_context


def hypotheses(dataset: ResearchDataset, analysis: Record, config: ResearchConfig) -> list[Record]:
    if dataset.manifest["dataset_type"] == "SYNTHETIC_QUALIFICATION":
        return []
    if dataset.manifest["dataset_type"] != "REAL_DEMO_OBSERVATION":
        raise ValueError("UNSUPPORTED_HYPOTHESIS_DATASET")
    # Unknown or pooled EA identities cannot support an EA-specific hypothesis.
    candidates = {r["candidate_id"] for r in dataset.episodes}
    known_scope = (
        len(candidates) == 1
        and None not in candidates
        and all(
            r["source_confidence"] == "KNOWN" and r["entry_time_known"] is True
            for r in dataset.episodes
        )
    )
    result = []
    for field in ("h1_ema20_distance_atr", "h1_ema50_distance_atr", "h1_ema200_distance_atr"):
        metric = analysis["market_context"][field]["direction_agreement"]
        n, known = metric["n"], metric["known_count"]
        by_session: dict[str, list[bool | None]] = {}
        for row in dataset.episodes:
            value = number(row[field])
            agrees = (
                None
                if value is None or value == 0 or row["direction"] not in ("BUY", "SELL")
                else (row["direction"] == "BUY") == (value > 0)
            )
            by_session.setdefault(row["session_id"], []).append(agrees)
        with arithmetic_context():
            coverage = Decimal(known) / n if n else Decimal(0)
            session_rates = [rate(v) for v in by_session.values()]
            sufficient_sessions = [
                r for r in session_rates if r["known_count"] >= config.preliminary_n
            ]
            status = "INSUFFICIENT_DATA"
            if (
                known_scope
                and known >= config.usable_n
                and coverage >= config.hypothesis_coverage
                and len(sufficient_sessions) >= config.minimum_sessions
            ):
                status = "WEAK_EVIDENCE"
                intervals = [metric["interval"], *(r["interval"] for r in sufficient_sessions)]
                if all(Decimal(v[0]) > config.agreement_threshold for v in intervals):
                    status = "SUPPORTED_BY_CURRENT_SAMPLE"
                elif all(Decimal(v[1]) < config.agreement_threshold for v in intervals):
                    status = "CONTRADICTED_BY_CURRENT_SAMPLE"
        metric_path = f"market_context.{field}.direction_agreement"
        item = BehaviorHypothesis.model_validate(
            dict(
                hypothesis_id=identity(
                    [dataset.dataset_hash, config.model_dump(mode="json"), field]
                ),
                hypothesis_type="TREND_ALIGNMENT",
                description=(
                    f"Observed entry direction agrees with the sign of {field} "
                    "more often than the prespecified fraction; association only, "
                    "not an EA rule."
                ),
                supporting_metrics=[metric_path] if status == "SUPPORTED_BY_CURRENT_SAMPLE" else [],
                contradicting_metrics=[metric_path]
                if status == "CONTRADICTED_BY_CURRENT_SAMPLE"
                else [],
                sample_size=n,
                known_count=known,
                missing_count=n - known,
                coverage=str(coverage),
                status=status,
            )
        ).model_dump(mode="json")
        item["session_evidence"] = {k: rate(v) for k, v in sorted(by_session.items())}
        item["limitations"] = [
            "Correlated episodes and confounding remain; thresholds are operational policy.",
            "No non-entry opportunity population; this is not proof of a filter or rule.",
            "Multiple descriptive hypotheses; no p-values or significance claims.",
        ]
        result.append(item)
    return result
