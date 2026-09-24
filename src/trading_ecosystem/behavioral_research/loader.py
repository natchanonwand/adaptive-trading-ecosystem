"""Fail-closed Phase 4C readback; source verification is offline and read-only."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from trading_ecosystem.behavioral_research.contracts import Record, ResearchConfig
from trading_ecosystem.features.dataset import validate


@dataclass(frozen=True)
class ResearchDataset:
    manifest: Record
    dataset_hash: str
    episodes: list[Record]
    entries: list[Record]
    outcomes: list[Record]


def load(path: Path, config: ResearchConfig) -> ResearchDataset:
    raw_manifest = (path / "manifest.json").read_bytes()
    manifest = validate(path)
    if raw_manifest != (path / "manifest.json").read_bytes():
        raise ValueError("FEATURE_MANIFEST_CHANGED_DURING_VALIDATION")
    if json.loads(raw_manifest) != manifest:
        raise ValueError("FEATURE_MANIFEST_CHANGED_DURING_VALIDATION")
    if manifest["dataset_type"] not in ("SYNTHETIC_QUALIFICATION", "REAL_DEMO_OBSERVATION"):
        raise ValueError("UNSUPPORTED_RESEARCH_DATASET_TYPE")
    tables: dict[str, list[Record]] = {}
    for name, meta in manifest["datasets"].items():
        data = (path / (name + ".parquet")).read_bytes()
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ValueError("FEATURE_BYTES_CHANGED_DURING_READ")
        tables[name] = [
            {k: json.loads(v) if k in ("quality", "availability") else v for k, v in row.items()}
            for row in pq.read_table(pa.BufferReader(data)).to_pylist()
        ]
    xs, ys = tables["episode_features"], tables["episode_outcomes"]

    def key(r: Record) -> tuple[str, str]:
        return str(r["session_id"]), str(r["episode_id"])

    if len({key(r) for r in xs}) != len(xs) or len({key(r) for r in ys}) != len(ys):
        raise ValueError("NONUNIQUE_RESEARCH_EPISODE_KEY")
    if {key(r) for r in xs} != {key(r) for r in ys}:
        raise ValueError("UNPAIRED_RESEARCH_EPISODE_OUTCOME")
    keys = {key(r) for r in xs}
    if any(key(r) not in keys for r in tables["entry_features"]):
        raise ValueError("ORPHAN_RESEARCH_ENTRY")
    xs = [
        r
        for r in xs
        if all(
            wanted is None or r[field] == wanted
            for field, wanted in (
                ("candidate_id", config.candidate_id),
                ("session_id", config.session_id),
                ("symbol", config.symbol),
            )
        )
    ]
    selected = {key(r) for r in xs}
    return ResearchDataset(
        manifest,
        hashlib.sha256(raw_manifest).hexdigest(),
        sorted(xs, key=key),
        sorted(
            (r for r in tables["entry_features"] if key(r) in selected), key=lambda r: r["row_id"]
        ),
        sorted((r for r in ys if key(r) in selected), key=key),
    )
