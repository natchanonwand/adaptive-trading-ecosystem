"""Deterministic evidence serialization; fresh directories only, independent readback."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from trading_ecosystem.behavioral_research.contracts import (
    Record,
    ResearchConfig,
    canonical,
    identity,
)
from trading_ecosystem.behavioral_research.engine import research


def packet(result: Record) -> Record:
    # Already aggregated: never exports input rows, tickets, account IDs or raw observations.
    return {
        k: result[k]
        for k in (
            "schema_version",
            "run_id",
            "dataset_hash",
            "feature_set_id",
            "dataset_type",
            "status",
            "research_config_hash",
            "code_version",
            "baseline_checkpoint",
            "seed",
            "source_session_ids",
            "selected_session_ids",
            "selected_candidates",
            "selected_symbols",
            "fingerprint",
            "hypotheses",
            "limitations",
            "real_ea_research_qualification",
            "content_hash",
        )
    }


def markdown(result: Record) -> str:
    warning = (
        "SOFTWARE VALIDATION DATA ONLY\n\nNO REAL EA BEHAVIORAL CONCLUSIONS"
        if result["dataset_type"] == "SYNTHETIC_QUALIFICATION"
        else "INSUFFICIENT DATA"
        if result["status"] == "INSUFFICIENT_DATA"
        else "DESCRIPTIVE ASSOCIATIONS ONLY — NO STRATEGY CLASSIFICATION"
    )
    lines = [
        "# Behavioral research",
        "",
        warning,
        "",
        "## Dataset provenance",
        "",
        f"Run: `{result['run_id']}`",
        f"Dataset type: `{result['dataset_type']}`",
        f"Feature set: `{result['feature_set_id']}`",
        f"Dataset hash: `{result['dataset_hash']}`",
        f"Config: `{result['research_config_hash']}`",
        "",
    ]
    for title, value in (
        ("Data quality and sample size", result["fingerprint"]["measurements"]["sample"]),
        (
            "Behavior fingerprint",
            {k: v for k, v in result["fingerprint"].items() if k != "measurements"},
        ),
        ("Temporal behavior", result["fingerprint"]["measurements"]["temporal"]),
        ("Direction behavior", result["fingerprint"]["measurements"]["direction"]),
        ("Position sizing behavior", result["fingerprint"]["measurements"]["volume"]),
        (
            "SL/TP behavior",
            {
                "initial": result["fingerprint"]["measurements"]["stops"],
                "first_observed_changes": result["fingerprint"]["measurements"]["stop_changes"],
            },
        ),
        ("Market context", result["fingerprint"]["measurements"]["market_context"]),
        (
            "Sequence behavior",
            {
                "spacing": result["fingerprint"]["measurements"]["spacing"],
                "prior_adverse": result["fingerprint"]["measurements"]["prior_adverse_progression"],
            },
        ),
        ("Outcome summary", result["fingerprint"]["measurements"]["outcomes"]),
        (
            "Retrospective outcome strata",
            result["fingerprint"]["measurements"]["retrospective_outcomes"],
        ),
        ("Associations", result["fingerprint"]["measurements"]["associations"]),
        ("Bin definitions", result["fingerprint"]["measurements"]["bin_definitions"]),
        ("Hypotheses", result["hypotheses"]),
    ):
        lines.extend(
            [
                "## " + title,
                "",
                "```json",
                json.dumps(value, indent=2, sort_keys=True, allow_nan=False),
                "```",
                "",
            ]
        )
    lines.extend(["## Limitations", "", *("- " + v for v in result["limitations"]), ""])
    return "\n".join(lines)


def artifacts(result: Record) -> dict[str, str]:
    return {
        "research.json": canonical(result) + "\n",
        "behavior_fingerprint.json": canonical(result["fingerprint"]) + "\n",
        "behavior_research_packet.json": canonical(packet(result)) + "\n",
        "report.md": markdown(result),
    }


def export(dataset: Path, output: Path, config: ResearchConfig) -> Record:
    if output.exists():
        raise ValueError("RESEARCH_EXPORT_ALREADY_EXISTS")
    result = research(dataset, config)
    files = artifacts(result)
    manifest = dict(
        run_id=result["run_id"],
        dataset_path=str(dataset.resolve()),
        dataset_hash=result["dataset_hash"],
        feature_set_id=result["feature_set_id"],
        research_config=config.model_dump(mode="json"),
        research_config_hash=result["research_config_hash"],
        code_version=result["code_version"],
        baseline_checkpoint=result["baseline_checkpoint"],
        seed=config.seed,
        created_at=datetime.now(UTC).isoformat(),
        created_at_basis="WALL_CLOCK_EXCLUDED_FROM_CONTENT_IDENTITY",
        dataset_type=result["dataset_type"],
        content_hash=result["content_hash"],
        files={name: hashlib.sha256(body.encode()).hexdigest() for name, body in files.items()},
    )
    output.mkdir(parents=True, exist_ok=False)
    for name, body in files.items():
        (output / name).write_bytes(body.encode())
    (output / "manifest.json").write_bytes((canonical(manifest) + "\n").encode())
    validate(output)
    return manifest


def validate(output: Path) -> Record:
    manifest: Record = json.loads((output / "manifest.json").read_bytes())
    config = ResearchConfig.model_validate(manifest["research_config"])
    result = research(Path(manifest["dataset_path"]), config)
    if set(manifest) != {
        "run_id",
        "dataset_path",
        "dataset_hash",
        "feature_set_id",
        "research_config",
        "research_config_hash",
        "code_version",
        "baseline_checkpoint",
        "seed",
        "created_at",
        "created_at_basis",
        "dataset_type",
        "content_hash",
        "files",
    }:
        raise ValueError("RESEARCH_MANIFEST_SCHEMA_MISMATCH")
    for key in (
        "run_id",
        "dataset_hash",
        "feature_set_id",
        "research_config_hash",
        "code_version",
        "baseline_checkpoint",
        "seed",
        "dataset_type",
        "content_hash",
    ):
        if manifest[key] != result[key]:
            raise ValueError("RESEARCH_IDENTITY_MISMATCH: " + key)
    stamp = datetime.fromisoformat(manifest["created_at"])
    if (
        stamp.tzinfo is None
        or stamp.utcoffset() != UTC.utcoffset(stamp)
        or manifest["created_at_basis"] != "WALL_CLOCK_EXCLUDED_FROM_CONTENT_IDENTITY"
    ):
        raise ValueError("INVALID_RESEARCH_CREATED_AT")
    expected = artifacts(result)
    if set(manifest["files"]) != set(expected):
        raise ValueError("RESEARCH_ARTIFACT_SET_MISMATCH")
    for name, body in expected.items():
        data = (output / name).read_bytes()
        if data != body.encode() or hashlib.sha256(data).hexdigest() != manifest["files"][name]:
            raise ValueError("RESEARCH_CANONICAL_READBACK_MISMATCH: " + name)
    if identity({k: v for k, v in result.items() if k != "content_hash"}) != result["content_hash"]:
        raise ValueError("RESEARCH_CONTENT_HASH_MISMATCH")
    return manifest
