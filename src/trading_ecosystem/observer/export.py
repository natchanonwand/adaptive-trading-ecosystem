"""Deterministic Parquet export with raw lineage, schema and independent readback."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import Connection, select

from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import timestamp
from trading_ecosystem.mt5.store import observations
from trading_ecosystem.observer.contracts import ObservationSession, content_id
from trading_ecosystem.observer.identity import instances
from trading_ecosystem.observer.replay import replay
from trading_ecosystem.observer.store import load_frames, scope
from trading_ecosystem.observer.summary import summarize

SCHEMA = pa.schema(
    [
        ("identity", pa.string()),
        ("session_id", pa.string()),
        ("record_kind", pa.string()),
        ("canonical_json", pa.string()),
    ]
)


def encoded(row: Record) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def export_session(conn: Connection, session: ObservationSession, output: Path) -> Record:
    if output.exists():
        raise ValueError("OBSERVER_EXPORT_ALREADY_EXISTS")
    retained = load_frames(conn, session)
    events, episodes = replay(session, retained)
    market = []
    for row in conn.execute(
        select(observations).where(
            observations.c.scope_id == scope(session).stream_id,
            observations.c.kind.in_(("EA_CONTEXT", "EA_WINDOW")),
        )
    ).mappings():
        if content_id(row["body"]) != row["body_hash"]:
            raise ValueError("OBSERVER_CONTEXT_HASH_MISMATCH")
        market.append({"identity": row["body_hash"], "kind": row["kind"], "body": row["body"]})
    ids = {r["identity"] for r in market}
    if any(
        e["context_reference"] is not None and e["context_reference"] not in ids for e in events
    ):
        raise ValueError("MISSING_EVENT_CONTEXT")
    for record in market:
        if record["kind"] == "EA_CONTEXT":
            if any(ref["window_id"] not in ids for ref in record["body"]["windows"].values()):
                raise ValueError("MISSING_CONTEXT_WINDOW")
    output.mkdir(parents=True)
    datasets = {
        "external_ea_events": [(r["event_id"], r["kind"], r) for r in events],
        "external_ea_episodes": [(r["episode_id"], "EPISODE", r) for r in episodes],
        "external_ea_market_context": [(r["identity"], r["kind"], r["body"]) for r in market],
        "external_ea_raw_frames": [
            (content_id(f.model_dump(mode="json")), "FRAME", f.model_dump(mode="json"))
            for f in retained
        ],
    }
    manifest: Record = {
        "schema_version": "EXTERNAL_EA_V1",
        "created_at": (retained[-1].observed_at if retained else session.started_at).isoformat(),
        "created_at_basis": "LAST_RAW_OBSERVATION_OR_SESSION_START",
        "session": session.model_dump(mode="json"),
        "config_hash": content_id(session.config.model_dump(mode="json")),
        "schema": str(SCHEMA),
        "pyarrow_version": pa.__version__,
        "qualification_eligible": False,
        "summary": summarize(episodes, events),
        "source_instances": instances(session, events),
        "datasets": {},
    }
    for name, records in datasets.items():
        rows = [
            {
                "identity": key,
                "session_id": str(session.session_id),
                "record_kind": kind,
                "canonical_json": encoded(body),
            }
            for key, kind, body in sorted(records, key=lambda x: x[0])
        ]
        table = pa.Table.from_pylist(rows, schema=SCHEMA)
        path = output / (name + ".parquet")
        pq.write_table(table, path, compression="zstd", version="2.6", use_dictionary=False)
        if pq.read_table(path).schema != SCHEMA or pq.read_table(path).to_pylist() != rows:
            raise ValueError("OBSERVER_PARQUET_READBACK_FAILURE")
        manifest["datasets"][name] = {
            "schema_version": manifest["schema_version"],
            "session_id": str(session.session_id),
            "observer_version": session.observer_version,
            "config_hash": manifest["config_hash"],
            "created_at": manifest["created_at"],
            "rows": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "content_identity": content_id(rows),
        }
    (output / "manifest.json").write_text(encoded(manifest) + "\n", encoding="utf-8")
    verify_export(output)
    return manifest


def verify_export(output: Path) -> Record:
    from trading_ecosystem.observer.contracts import Frame

    manifest: Record = json.loads((output / "manifest.json").read_text())
    datasets = {}
    for name, expected in manifest["datasets"].items():
        if name not in {
            "external_ea_events",
            "external_ea_episodes",
            "external_ea_market_context",
            "external_ea_raw_frames",
        }:
            raise ValueError("UNKNOWN_OBSERVER_DATASET")
        path = output / (name + ".parquet")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError("OBSERVER_PARQUET_HASH_MISMATCH")
        table = pq.read_table(path)
        rows = table.to_pylist()
        if (
            table.schema != SCHEMA
            or len(rows) != expected["rows"]
            or content_id(rows) != expected["content_identity"]
        ):
            raise ValueError("OBSERVER_SCHEMA_OR_CONTENT_MISMATCH")
        datasets[name] = [json.loads(r["canonical_json"]) for r in rows]
    session = ObservationSession.model_validate(manifest["session"])
    if manifest["schema_version"] != "EXTERNAL_EA_V1" or manifest["config_hash"] != content_id(
        session.config.model_dump(mode="json")
    ):
        raise ValueError("OBSERVER_MANIFEST_CONTRACT_MISMATCH")
    market = {content_id(row): row for row in datasets["external_ea_market_context"]}
    for context in market.values():
        if "as_of" not in context:
            continue
        as_of = utc_timestamp(context["as_of"])
        if context["quote"] and utc_timestamp(context["quote"]["timestamp"]) > as_of:
            raise ValueError("FUTURE_QUOTE_IN_EXPORT")
        for ref in context["windows"].values():
            window = market[ref["window_id"]]
            if any(
                timestamp(bar["time"]) + timedelta(seconds=window["duration_seconds"]) > as_of
                for bar in window["bars"]
            ):
                raise ValueError("FUTURE_CANDLE_IN_EXPORT")
    frames = tuple(
        sorted(
            (Frame.model_validate(r) for r in datasets["external_ea_raw_frames"]),
            key=lambda f: f.sequence,
        )
    )
    events, episodes = replay(session, frames)
    created_at = (frames[-1].observed_at if frames else session.started_at).isoformat()
    if manifest["created_at"] != created_at:
        raise ValueError("OBSERVER_CREATION_TIME_MISMATCH")
    for dataset in manifest["datasets"].values():
        if any(
            dataset[key] != value
            for key, value in {
                "schema_version": "EXTERNAL_EA_V1",
                "session_id": str(session.session_id),
                "observer_version": session.observer_version,
                "config_hash": manifest["config_hash"],
                "created_at": created_at,
            }.items()
        ):
            raise ValueError("OBSERVER_DATASET_METADATA_MISMATCH")
    for event in events:
        ref = event["context_reference"]
        if ref is not None:
            context = market[ref]
            if utc_timestamp(context["as_of"]) > utc_timestamp(
                event["broker_at"] or event["observed_at"]
            ):
                raise ValueError("FUTURE_EVENT_CONTEXT")
    if (
        sorted(events, key=lambda r: r["event_id"]) != datasets["external_ea_events"]
        or episodes != datasets["external_ea_episodes"]
    ):
        raise ValueError("OBSERVER_EXPORT_REPLAY_MISMATCH")
    if summarize(episodes, events) != manifest["summary"]:
        raise ValueError("OBSERVER_SUMMARY_MISMATCH")
    if instances(session, events) != manifest["source_instances"]:
        raise ValueError("OBSERVER_INSTANCE_REPLAY_MISMATCH")
    return manifest
