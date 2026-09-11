"""Explicit Decimal Parquet schema, exclusive writes, independent content identity."""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from trading_ecosystem.datasets.contracts import ARITHMETIC_VERSION, SCHEMA_VERSION, Bar, Window
from trading_ecosystem.domain.canonical import canonical_bytes


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def object_hash(value: object) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("xb") as stream:
        stream.write(json_bytes(value))


def read_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def content_id(bars: Sequence[Bar], window: Window, asset: str) -> str:
    digest = hashlib.sha256()
    digest.update(
        canonical_bytes(
            {
                "schema": SCHEMA_VERSION,
                "arithmetic": ARITHMETIC_VERSION,
                "asset": asset,
                **window.model_dump(),
            }
        )
    )
    for bar in bars:
        # Operational provenance belongs to the manifest, never normalized identity.
        data = bar.model_dump(
            exclude={
                "dataset_id",
                "retrieved_at",
                "instrument_metadata_reference",
                "source_version",
            }
        )
        digest.update(canonical_bytes(data))
    return digest.hexdigest()


def schema() -> pa.Schema:
    fields = []
    for name in Bar.model_fields:
        dtype: pa.DataType = pa.string()
        if name in {"open", "high", "low", "close"}:
            dtype = pa.decimal128(34, 18)
        elif name in {"open_time", "close_time", "available_at", "retrieved_at"}:
            dtype = pa.timestamp("us", tz="UTC")
        elif name in {"tick_volume", "spread_points", "real_volume"}:
            dtype = pa.int64()
        elif name == "quality_flags":
            dtype = pa.list_(pa.field("element", pa.string()))
        fields.append(pa.field(name, dtype, nullable=name == "source_version"))
    return pa.schema(
        fields,
        metadata={
            b"schema_version": SCHEMA_VERSION.encode(),
            b"arithmetic_version": ARITHMETIC_VERSION.encode(),
        },
    )


def write_parquet(path: Path, bars: Sequence[Bar]) -> None:
    table = pa.Table.from_pylist([bar.model_dump() for bar in bars], schema=schema())
    with path.open("xb") as stream:
        pq.write_table(table, stream, compression="zstd", version="2.6")


def read_parquet(path: Path) -> tuple[Bar, ...]:
    table = pq.read_table(path)
    if not table.schema.equals(schema(), check_metadata=True):
        raise ValueError("PARQUET_SCHEMA_MISMATCH")
    return tuple(Bar.model_validate(row) for row in table.to_pylist())


def code_hash() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for folder in ("datasets", "discovery", "domain"):
        for path in sorted((root / folder).glob("*.py")):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()
