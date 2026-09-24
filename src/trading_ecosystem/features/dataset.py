"""Versioned wide Parquet tables, fail-closed validation and independent source rebuild."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.features.builder import build
from trading_ecosystem.features.contracts import BUILDER_VERSION, SCHEMA_VERSION, BuildConfig
from trading_ecosystem.features.registry import BUILDER_SOURCE_HASH, CATALOG, FEATURE_SET_ID
from trading_ecosystem.features.statistics import describe
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import number
from trading_ecosystem.observer.contracts import content_id
from trading_ecosystem.observer.export import encoded

X_KEYS = (
    "row_id",
    "session_id",
    "episode_id",
    "entry_event_id",
    "candidate_id",
    "symbol",
    "direction",
    "entry_observed_at",
    "prediction_cutoff",
    "sequence_group_id",
    "availability",
    "quality",
)
Y_KEYS = ("row_id", "session_id", "episode_id", "available_at", "closed_at")


def validate_rows(rows: list[Record], *, causal: bool) -> None:
    definitions = [d for d in CATALOG if d.causal == causal]
    names = {d.name for d in definitions}
    expected = set(X_KEYS if causal else Y_KEYS) | names
    if len({r.get("row_id") for r in rows}) != len(rows):
        raise ValueError("DUPLICATE_FEATURE_PRIMARY_KEY")
    for row in rows:
        if set(row) != expected:
            raise ValueError("FEATURE_SCHEMA_MISMATCH")
        if any(
            not isinstance(row[k], str) or not row[k]
            for k in ("row_id", "session_id", "episode_id")
        ):
            raise ValueError("INVALID_FEATURE_IDENTITY")
        for d in definitions:
            value = row[d.name]
            if value is None:
                continue
            if d.dtype == "decimal":
                if not isinstance(value, str) or not number(value).is_finite():
                    raise ValueError("INVALID_DECIMAL_FEATURE")
            elif d.dtype == "integer" and type(value) is not int:
                raise ValueError("INVALID_INTEGER_FEATURE")
            elif d.dtype == "boolean" and type(value) is not bool:
                raise ValueError("INVALID_BOOLEAN_FEATURE")
            elif d.dtype == "string" and not isinstance(value, str):
                raise ValueError("INVALID_STRING_FEATURE")
            elif d.dtype == "decimal_sequence" and (
                not isinstance(value, list)
                or any(not isinstance(v, str) or not number(v).is_finite() for v in value)
            ):
                raise ValueError("INVALID_SEQUENCE_FEATURE")
        if causal:
            cutoff = utc_timestamp(row["prediction_cutoff"])
            if (
                utc_timestamp(row["entry_observed_at"]) != cutoff
                or set(row["availability"]) != names
            ):
                raise ValueError("INVALID_FEATURE_AVAILABILITY_SCHEMA")
            for name in names:
                at = row["availability"][name]
                if row[name] is None:
                    if at is not None or not row["quality"]["missing"].get(name):
                        raise ValueError("UNDOCUMENTED_NULL_FEATURE")
                elif at is None or utc_timestamp(at) > cutoff:
                    raise ValueError("FEATURE_LEAKAGE")


def schema(causal: bool) -> pa.Schema:
    fields: list[pa.Field[Any]] = [pa.field(k, pa.string()) for k in (X_KEYS if causal else Y_KEYS)]
    for d in CATALOG:
        if d.causal == causal:
            dtype = (
                pa.int64()
                if d.dtype == "integer"
                else pa.bool_()
                if d.dtype == "boolean"
                else pa.list_(pa.field("element", pa.string()))
                if d.dtype == "decimal_sequence"
                else pa.string()
            )
            fields.append(pa.field(d.name, dtype, metadata={b"logical_type": d.dtype.encode()}))
    return pa.schema(fields)


def export(paths: list[Path], output: Path, config: BuildConfig) -> Record:
    if output.exists():
        raise ValueError("FEATURE_EXPORT_ALREADY_EXISTS")
    tables, sources = build(paths, config)
    raw_tables, _ = build(paths, config, raw_replay=True)
    if tables != raw_tables:
        raise ValueError("RAW_MATERIALIZED_FEATURE_MISMATCH")
    if not sources:
        raise ValueError("FEATURE_SOURCE_REQUIRED")
    built_at = max((s["created_at"] for s in sources), key=utc_timestamp)
    manifest: Record = dict(
        schema_version=SCHEMA_VERSION,
        feature_set_id=FEATURE_SET_ID,
        feature_builder_version=BUILDER_VERSION,
        builder_source_hash=BUILDER_SOURCE_HASH,
        config=config.model_dump(mode="json"),
        config_hash=content_id(config.model_dump(mode="json")),
        built_at=built_at,
        created_at=built_at,
        build_time_basis="LATEST_IMMUTABLE_SOURCE_OBSERVATION",
        sources=sources,
        session_ids=[s["session_id"] for s in sources],
        dataset_type=config.dataset_type,
        catalog=[d.model_dump(mode="json") for d in CATALOG],
        datasets={},
        causal_feature_count=sum(d.causal for d in CATALOG),
        outcome_field_count=sum(not d.causal for d in CATALOG),
        qualification_eligible=False,
        adx="DEFERRED",
        summary={},
    )
    output.mkdir(parents=True)
    for name, rows in tables.items():
        causal = name != "episode_outcomes"
        validate_rows(rows, causal=causal)
        if name != "entry_features" and len({r["episode_id"] for r in rows}) != len(rows):
            raise ValueError("DUPLICATE_EPISODE_ROW")
        serialized = [
            {k: encoded(v) if k in ("availability", "quality") else v for k, v in r.items()}
            for r in rows
        ]
        path = output / (name + ".parquet")
        table = pa.Table.from_pylist(serialized, schema=schema(causal))
        pq.write_table(table, path, compression="zstd", use_dictionary=False, version="2.6")
        if pq.read_table(path).to_pylist() != serialized:
            raise ValueError("FEATURE_PARQUET_READBACK_FAILURE")
        manifest["datasets"][name] = dict(
            dataset_name=name,
            schema_version=SCHEMA_VERSION,
            feature_set_id=FEATURE_SET_ID,
            session_ids=manifest["session_ids"],
            rows=len(rows),
            columns=len(table.schema),
            content_hash=content_id(rows),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            created_at=built_at,
            config_hash=manifest["config_hash"],
        )
        manifest["summary"][name] = describe(rows, causal=causal)
    (output / "manifest.json").write_text(encoded(manifest) + "\n", encoding="utf-8")
    validate(output)
    return manifest


def validate(output: Path) -> Record:
    manifest: Record = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    config = BuildConfig.model_validate(manifest["config"])
    if (
        manifest["schema_version"] != SCHEMA_VERSION
        or manifest["feature_set_id"] != FEATURE_SET_ID
        or manifest["feature_builder_version"] != BUILDER_VERSION
        or manifest["builder_source_hash"] != BUILDER_SOURCE_HASH
        or manifest["config_hash"] != content_id(config.model_dump(mode="json"))
        or manifest["catalog"] != [d.model_dump(mode="json") for d in CATALOG]
    ):
        raise ValueError("FEATURE_VERSION_OR_CONFIG_MISMATCH")
    rebuilt, sources = build(
        [Path(s["path"]) for s in manifest["sources"]], config, raw_replay=True
    )
    if sources != manifest["sources"] or set(manifest["datasets"]) != set(rebuilt):
        raise ValueError("FEATURE_SOURCE_IDENTITY_MISMATCH")
    built_at = max((s["created_at"] for s in sources), key=utc_timestamp)
    if (
        manifest["built_at"] != built_at
        or manifest["created_at"] != built_at
        or manifest["dataset_type"] != config.dataset_type
        or manifest["session_ids"] != [s["session_id"] for s in sources]
        or manifest["causal_feature_count"] != sum(d.causal for d in CATALOG)
        or manifest["outcome_field_count"] != sum(not d.causal for d in CATALOG)
        or manifest["qualification_eligible"] is not False
    ):
        raise ValueError("FEATURE_MANIFEST_METADATA_MISMATCH")
    for name, expected in manifest["datasets"].items():
        if any(
            expected[k] != v
            for k, v in {
                "dataset_name": name,
                "schema_version": SCHEMA_VERSION,
                "feature_set_id": FEATURE_SET_ID,
                "session_ids": manifest["session_ids"],
                "created_at": built_at,
                "config_hash": manifest["config_hash"],
            }.items()
        ):
            raise ValueError("FEATURE_DATASET_METADATA_MISMATCH")
        path = output / (name + ".parquet")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError("FEATURE_FILE_HASH_MISMATCH")
        table = pq.read_table(path)
        rows = [
            {k: json.loads(v) if k in ("availability", "quality") else v for k, v in r.items()}
            for r in table.to_pylist()
        ]
        causal = name != "episode_outcomes"
        validate_rows(rows, causal=causal)
        if (
            not table.schema.equals(schema(causal), check_metadata=True)
            or rows != rebuilt[name]
            or content_id(rows) != expected["content_hash"]
            or len(rows) != expected["rows"]
            or len(table.schema) != expected["columns"]
            or describe(rows, causal=causal) != manifest["summary"][name]
        ):
            raise ValueError("FEATURE_CANONICAL_REBUILD_MISMATCH")
    return manifest
