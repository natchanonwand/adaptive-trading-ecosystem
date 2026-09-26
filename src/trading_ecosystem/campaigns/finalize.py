"""Freeze real evidence and rebuild existing Phase 4B/4C/4D pipeline twice offline."""

import hashlib
import json
from pathlib import Path

from sqlalchemy import Engine

from trading_ecosystem.behavioral_research.loader import load
from trading_ecosystem.behavioral_research.reports import export as research_export
from trading_ecosystem.behavioral_research.reports import validate as research_validate
from trading_ecosystem.campaigns.contracts import RealEaQualificationCampaign
from trading_ecosystem.campaigns.diagnostics import diagnostics
from trading_ecosystem.campaigns.journal import read, write_new
from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.features.builder import read_source
from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.features.dataset import export as feature_export
from trading_ecosystem.features.dataset import validate as feature_validate
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.observer.export import export_session, verify_export
from trading_ecosystem.observer.store import get_session


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ready(root: Path) -> tuple[RealEaQualificationCampaign, Record]:
    spec = RealEaQualificationCampaign.model_validate_json((root / "campaign.json").read_bytes())
    rows = read(root)
    if (
        not spec.metadata.ready()
        or not rows
        or rows[0]["kind"] != "START"
        or rows[-1]["kind"] != "STOP"
    ):
        raise ValueError("CAMPAIGN_METADATA_OR_STOP_REQUIRED")
    stop = rows[-1]["body"]
    if (
        stop["status"] != "STOPPED_RECONCILED"
        or stop["origin"] != "NATIVE_DEMO_READ_ONLY"
        or rows[0]["body"]["origin"] != "NATIVE_DEMO_READ_ONLY"
        or any(r["kind"] == "POLL" and not r["body"]["success"] for r in rows)
        or any(r["kind"] == "GAP" for r in rows)
    ):
        raise ValueError("CAMPAIGN_NOT_ELIGIBLE_FOR_REAL_QUALIFICATION")
    start = rows[0]["body"]
    if (
        not start.get("gate", {}).get("passed")
        or sum(r["kind"] == "START" for r in rows) != 1
        or sum(r["kind"] == "STOP" for r in rows) != 1
        or not spec.window_start <= utc_timestamp(stop["started_at"]) < spec.window_end
        or utc_timestamp(stop["ended_at"]) < utc_timestamp(stop["started_at"])
        or stop["polls"] != sum(r["kind"] == "POLL" for r in rows)
        or stop["polls"] < 1
        or any(r["kind"] == "HEALTH" and not r["body"]["passed"] for r in rows)
    ):
        raise ValueError("CAMPAIGN_CONTINUITY_PROOF_INCOMPLETE")
    return spec, stop


def finalize(root: Path, engine: Engine) -> Record:
    if (root / "manifest.json").exists() or (root / "raw").exists():
        raise ValueError("PRESERVE_FINAL_OR_INTERRUPTED_CAMPAIGN_EXPORT")
    spec, stop = ready(root)
    with engine.connect() as conn:
        session = get_session(conn, spec.campaign_id)
        if session.account_scope != spec.account_scope or session.config != spec.observer_config:
            raise ValueError("CAMPAIGN_OBSERVER_IDENTITY_MISMATCH")
        first = export_session(conn, session, root / "raw")
        second = export_session(conn, session, root / "raw-repeat")
    if first != second:
        raise ValueError("RAW_REPLAY_NONDETERMINISM")
    diagnostics(spec, read_source(root / "raw", raw_replay=True), [], stop)
    feature_config = BuildConfig(
        dataset_type="REAL_DEMO_OBSERVATION", provenance_reference=str(spec.campaign_id)
    )
    a = feature_export([root / "raw"], root / "features", feature_config)
    b = feature_export([root / "raw"], root / "features-repeat", feature_config)
    if a != b:
        raise ValueError("REAL_FEATURE_REBUILD_MISMATCH")
    r1 = research_export(root / "features", root / "research", spec.research_config)
    r2 = research_export(root / "features", root / "research-repeat", spec.research_config)
    if r1["content_hash"] != r2["content_hash"] or r1["files"] != r2["files"]:
        raise ValueError("REAL_RESEARCH_REBUILD_MISMATCH")
    summary = summarize(root, spec, stop)
    write_new(root / "summary.json", summary)
    files = {
        p.relative_to(root).as_posix(): file_hash(p) for p in sorted(root.rglob("*")) if p.is_file()
    }
    manifest = dict(
        campaign_id=str(spec.campaign_id),
        dataset_type="REAL_DEMO_OBSERVATION",
        status="FROZEN",
        files=files,
    )
    write_new(root / "manifest.json", manifest)
    validate(root)
    return summary


def summarize(root: Path, spec: RealEaQualificationCampaign, stop: Record) -> Record:
    source = read_source(root / "raw", raw_replay=True)
    dataset = load(root / "features", spec.research_config)
    r1 = json.loads((root / "research" / "manifest.json").read_bytes())
    result = json.loads((root / "research" / "research.json").read_bytes())
    candidate = spec.metadata.candidate.ea_id
    known = [
        e
        for e in source["events"]
        if e["attribution"]["confidence"] == "KNOWN"
        and e["attribution"]["source"] == "EXTERNAL_EA"
        and e["attribution"]["candidate_id"] == candidate
    ]
    episodes = [
        e
        for e in source["episodes"]
        if e["attribution"]["candidate_id"] == candidate
        and e["attribution"]["confidence"] == "KNOWN"
    ]
    summary = dict(
        campaign_id=str(spec.campaign_id),
        dataset_type="REAL_DEMO_OBSERVATION",
        status="COMPLETE",
        sample=result["fingerprint"]["measurements"]["sample"],
        real_ea_research_qualification="INSUFFICIENT"
        if result["fingerprint"]["measurements"]["sample"]["sufficiency"] == "INSUFFICIENT"
        else "QUALIFIED",
        qualification_basis="PIPELINE_AND_SAMPLE_SUFFICIENCY_ONLY_NOT_STRATEGY_TRUTH",
        raw_frames=len(source["frames"]),
        lifecycle_events=len(source["events"]),
        attributed_events=len(known),
        unknown_or_excluded_events=len(source["events"]) - len(known),
        episodes=len(episodes),
        completed_episodes=sum(e["closed_at"] is not None for e in episodes),
        open_censored_episodes=sum(e["closed_at"] is None for e in episodes),
        entry_events=sum(e["kind"] in {"POSITION_OPENED", "POSITION_INCREASED"} for e in known),
        distinct_observed_entry_days=len(
            {
                (e["broker_at"] or e["observed_at"])[:10]
                for e in known
                if e["kind"] in {"POSITION_OPENED", "POSITION_INCREASED"}
            }
        ),
        recovered_events=sum(e["recovered_state"] for e in source["events"]),
        observation_performance=stop,
        exit_reason_policy="BROKER_DEAL_REASON_ONLY; NO_PRICE_PROXIMITY_INFERENCE",
        basket_close="NOT_IDENTIFIABLE_WITHOUT_BASKET_MEMBERSHIP",
        costs_basis="OBSERVED_COMMISSION_FEE_SWAP_WITH_UNKNOWN_COUNTS",
        research_run_id=r1["run_id"],
        feature_set_id=spec.feature_set_id,
        diagnostics=diagnostics(spec, source, dataset.entries, stop),
    )
    return summary


def validate(root: Path) -> Record:
    manifest: Record = json.loads((root / "manifest.json").read_bytes())
    spec, stop = ready(root)
    actual = {
        p.relative_to(root).as_posix(): file_hash(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and p != root / "manifest.json"
    }
    if (
        manifest["files"] != actual
        or manifest["campaign_id"] != str(spec.campaign_id)
        or manifest["dataset_type"] != "REAL_DEMO_OBSERVATION"
        or manifest.get("status") != "FROZEN"
    ):
        raise ValueError("CAMPAIGN_FROZEN_HASH_MISMATCH")
    for name in ("raw", "raw-repeat"):
        verify_export(root / name)
    for name in ("features", "features-repeat"):
        features = feature_validate(root / name)
        expected = BuildConfig(
            dataset_type="REAL_DEMO_OBSERVATION", provenance_reference=str(spec.campaign_id)
        ).model_dump(mode="json")
        if (
            features["config"] != expected
            or features["session_ids"] != [str(spec.campaign_id)]
            or len(features["sources"]) != 1
            or Path(features["sources"][0]["path"]).resolve() != (root / "raw").resolve()
        ):
            raise ValueError("CAMPAIGN_FEATURE_LINEAGE_MISMATCH")
    for name in ("research", "research-repeat"):
        research = research_validate(root / name)
        if (
            research["research_config"] != spec.research_config.model_dump(mode="json")
            or Path(research["dataset_path"]).resolve() != (root / "features").resolve()
            or research["dataset_type"] != "REAL_DEMO_OBSERVATION"
        ):
            raise ValueError("CAMPAIGN_RESEARCH_LINEAGE_MISMATCH")
    for pair in (("raw", "raw-repeat"), ("features", "features-repeat")):
        one, two = [json.loads((root / n / "manifest.json").read_bytes()) for n in pair]
        if one != two:
            raise ValueError("CAMPAIGN_REBUILD_MISMATCH")
    one, two = [
        json.loads((root / n / "manifest.json").read_bytes())
        for n in ("research", "research-repeat")
    ]
    if one["content_hash"] != two["content_hash"] or one["files"] != two["files"]:
        raise ValueError("CAMPAIGN_RESEARCH_REBUILD_MISMATCH")
    if json.loads((root / "summary.json").read_bytes()) != summarize(root, spec, stop):
        raise ValueError("CAMPAIGN_SUMMARY_REBUILD_MISMATCH")
    return manifest
