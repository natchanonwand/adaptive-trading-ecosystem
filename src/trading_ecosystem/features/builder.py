"""Offline source verification and independent raw/materialized rebuild paths."""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.features.families import causal_features
from trading_ecosystem.features.outcomes import episode_outcome
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.observer.contracts import Frame, ObservationSession, content_id
from trading_ecosystem.observer.export import verify_export
from trading_ecosystem.observer.replay import replay


def read_source(path: Path, raw_replay: bool = False) -> Record:
    manifest = verify_export(path)
    tables = {
        name: [
            json.loads(r["canonical_json"])
            for r in pq.read_table(path / (name + ".parquet")).to_pylist()
        ]
        for name in manifest["datasets"]
    }
    frames = tuple(
        sorted(
            (Frame.model_validate(r) for r in tables["external_ea_raw_frames"]),
            key=lambda f: f.sequence,
        )
    )
    session = ObservationSession.model_validate(manifest["session"])
    events, episodes = (
        replay(session, frames)
        if raw_replay
        else (tables["external_ea_events"], tables["external_ea_episodes"])
    )
    return dict(
        manifest=manifest,
        manifest_hash=hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest(),
        path=path.as_posix(),
        frames=frames,
        events=events,
        episodes=episodes,
        market={content_id(r): r for r in tables["external_ea_market_context"]},
        session=session,
    )


def build_source(source: Record, config: BuildConfig) -> dict[str, list[Record]]:
    session: ObservationSession = source["session"]
    if config.dataset_type == "REAL_DEMO_OBSERVATION" and any(
        "FAKE" in (c.attribution_reference or "").upper() or "FIXTURE" in c.ea_id.upper()
        for c in session.config.candidates
    ):
        raise ValueError("SYNTHETIC_SOURCE_CANNOT_BECOME_REAL")
    tables: dict[str, list[Record]] = {
        "episode_features": [],
        "entry_features": [],
        "episode_outcomes": [],
    }
    events: list[Record] = source["events"]
    for episode in source["episodes"]:
        tickets = set(episode["deal_tickets"])
        entries = sorted(
            [
                e
                for e in events
                if e["kind"] in {"POSITION_OPENED", "POSITION_INCREASED"}
                and e["values"].get("deal_ticket") in tickets
            ],
            key=lambda e: (e["broker_at"], e["event_id"]),
        )
        fallback = sorted(
            [
                e
                for e in events
                if e["kind"] == "POSITION_STATE_OBSERVED"
                and e["position_id"] == episode["position_id"]
                and utc_timestamp(e["observed_at"]) <= utc_timestamp(episode["first_seen_at"])
            ],
            key=lambda e: e["observed_at"],
        )
        episode_entry = next((e for e in entries if e["kind"] == "POSITION_OPENED"), None)
        if episode_entry is None and fallback:
            episode_entry = fallback[-1]
        if episode_entry is None:
            raise ValueError("EPISODE_WITHOUT_ENTRY_OR_RECOVERY_ANCHOR")
        selected = entries if episode_entry in entries else [episode_entry, *entries]
        for event in selected:
            a = event["attribution"]
            candidate = a.get("candidate_id") if a.get("confidence") == "KNOWN" else None
            key = dict(
                session_id=str(session.session_id),
                episode_id=episode["episode_id"],
                entry_event_id=event["event_id"],
                candidate_id=candidate,
                symbol=event["symbol"],
                direction=event["values"].get("direction"),
                entry_observed_at=event["observed_at"],
                prediction_cutoff=event["observed_at"],
                sequence_group_id=content_id([str(session.session_id), candidate, event["symbol"]]),
            )
            values, available, quality = causal_features(
                event, source["frames"], source["market"], events, config
            )
            row = {**key, **values, "availability": available, "quality": quality}
            if event["kind"] in {"POSITION_OPENED", "POSITION_INCREASED"}:
                tables["entry_features"].append(
                    {
                        "row_id": content_id(["entry", str(session.session_id), event["event_id"]]),
                        **row,
                    }
                )
            if event["event_id"] == episode_entry["event_id"]:
                tables["episode_features"].append({"row_id": episode["episode_id"], **row})
        tables["episode_outcomes"].append(
            dict(
                row_id=episode["episode_id"],
                session_id=str(session.session_id),
                episode_id=episode["episode_id"],
                available_at=source["manifest"]["created_at"],
                closed_at=episode["closed_at"],
                **episode_outcome(episode, events),
            )
        )
    for rows in tables.values():
        rows.sort(key=lambda r: r["row_id"])
    return tables


def build(
    paths: list[Path], config: BuildConfig, *, raw_replay: bool = False
) -> tuple[dict[str, list[Record]], list[Record]]:
    tables: dict[str, list[Record]] = {
        "episode_features": [],
        "entry_features": [],
        "episode_outcomes": [],
    }
    sources: list[Record] = []
    seen: dict[str, str] = {}
    for path in sorted(set(paths)):
        source = read_source(path, raw_replay)
        sid = str(source["session"].session_id)
        if sid in seen:
            if seen[sid] != source["manifest_hash"]:
                raise ValueError("CONFLICTING_SESSION_EXPORT")
            continue
        seen[sid] = source["manifest_hash"]
        generated = build_source(source, config)
        for name, rows in generated.items():
            tables[name].extend(rows)
        sources.append(
            dict(
                path=path.as_posix(),
                session_id=sid,
                observer_version=source["session"].observer_version,
                source_manifest_hash=source["manifest_hash"],
                created_at=source["manifest"]["created_at"],
                input_episodes=len(source["episodes"]),
                market_context_rows=len(source["market"]),
            )
        )
    for rows in tables.values():
        rows.sort(key=lambda r: r["row_id"])
    return tables, sorted(sources, key=lambda r: r["session_id"])
