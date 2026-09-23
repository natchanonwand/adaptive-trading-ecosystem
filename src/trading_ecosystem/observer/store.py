"""Session-scoped immutable frames reference existing MT5 raw observation storage."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, Connection, Engine, Integer, MetaData, String, Table, Uuid, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.schema import CreateSchema

from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.monitoring.contracts import Scope
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.store import observations
from trading_ecosystem.observer.contracts import Frame, ObservationSession, content_id
from trading_ecosystem.observer.replay import replay

metadata = MetaData(schema="external_ea")
sessions = Table(
    "observation_sessions",
    metadata,
    Column("session_id", Uuid, primary_key=True),
    Column("body", JSONB, nullable=False),
    Column("body_hash", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("heartbeat", JSONB, nullable=False),
)
frames = Table(
    "raw_frame_refs",
    metadata,
    Column("session_id", Uuid, primary_key=True),
    Column("sequence", Integer, primary_key=True),
    Column("raw_hash", String(64), nullable=False),
)
events = Table(
    "behavior_events",
    metadata,
    Column("session_id", Uuid, primary_key=True),
    Column("event_id", String(64), primary_key=True),
    Column("body", JSONB, nullable=False),
)
episodes = Table(
    "trade_episodes",
    metadata,
    Column("session_id", Uuid, primary_key=True),
    Column("episode_id", String(64), primary_key=True),
    Column("body", JSONB, nullable=False),
)


def install(engine: Engine) -> None:
    from trading_ecosystem.mt5.store import install as install_raw

    install_raw(engine)
    with engine.begin() as conn:
        conn.execute(CreateSchema("external_ea", if_not_exists=True))
        metadata.create_all(conn)


def scope(session: ObservationSession) -> Scope:
    return Scope(environment="DEMO", account_id=session.account_scope, run_id=session.session_id)


def register(conn: Connection, session: ObservationSession) -> None:
    body = session.model_dump(mode="json")
    conn.execute(
        insert(sessions)
        .values(
            session_id=session.session_id,
            body=body,
            body_hash=content_id(body),
            status="STARTING",
            heartbeat={},
        )
        .on_conflict_do_nothing()
    )
    existing = (
        conn.execute(select(sessions).where(sessions.c.session_id == session.session_id))
        .mappings()
        .one()
    )
    if existing["body_hash"] != content_id(body) or existing["body"] != body:
        raise ValueError("IMMUTABLE_OBSERVER_SESSION_CONFLICT")


def raw(
    conn: Connection, session: ObservationSession, kind: str, body: Record, at: datetime
) -> str:
    key = content_id(body)
    conn.execute(
        insert(observations)
        .values(
            scope_id=scope(session).stream_id,
            kind=kind,
            external_id=key,
            body_hash=key,
            observed_at=at,
            body=body,
        )
        .on_conflict_do_nothing()
    )
    return key


def load_frames(conn: Connection, session: ObservationSession) -> tuple[Frame, ...]:
    rows = (
        conn.execute(
            select(frames.c.sequence, frames.c.raw_hash, observations.c.body)
            .join(
                observations,
                (observations.c.body_hash == frames.c.raw_hash)
                & (observations.c.scope_id == scope(session).stream_id)
                & (observations.c.kind == "EA_FRAME"),
            )
            .where(frames.c.session_id == session.session_id)
            .order_by(frames.c.sequence)
        )
        .mappings()
        .all()
    )
    result = []
    for row in rows:
        if digest(canonical_bytes(row["body"])) != row["raw_hash"]:
            raise ValueError("OBSERVER_RAW_INTEGRITY_FAILURE")
        result.append(Frame.model_validate(row["body"]))
    if len(result) != len(
        conn.execute(
            select(frames.c.sequence).where(frames.c.session_id == session.session_id)
        ).all()
    ):
        raise ValueError("MISSING_OBSERVER_RAW_FRAME")
    return tuple(result)


def append(
    conn: Connection, session: ObservationSession, frame: Frame, windows: dict[str, Record]
) -> tuple[int, int]:
    conn.execute(
        select(sessions.c.session_id)
        .where(sessions.c.session_id == session.session_id)
        .with_for_update()
    ).one()
    for key, window in windows.items():
        if key != content_id(window):
            raise ValueError("CONTEXT_WINDOW_HASH_MISMATCH")
        raw(conn, session, "EA_WINDOW", window, frame.observed_at)
    for context in frame.contexts.values():
        raw(conn, session, "EA_CONTEXT", context, frame.observed_at)
    key = raw(conn, session, "EA_FRAME", frame.model_dump(mode="json"), frame.observed_at)
    conn.execute(
        insert(frames)
        .values(session_id=session.session_id, sequence=frame.sequence, raw_hash=key)
        .on_conflict_do_nothing()
    )
    stored = conn.execute(
        select(frames.c.raw_hash).where(
            frames.c.session_id == session.session_id, frames.c.sequence == frame.sequence
        )
    ).scalar_one()
    if stored != key:
        raise ValueError("OBSERVER_FRAME_SEQUENCE_CONFLICT")
    lifecycle, grouped = replay(session, load_frames(conn, session))
    # Derived rows are rebuildable; immutable raw observations are never rewritten.
    for table, rows, field in ((events, lifecycle, "event_id"), (episodes, grouped, "episode_id")):
        conn.execute(table.delete().where(table.c.session_id == session.session_id))
        if rows:
            conn.execute(
                table.insert(),
                [{"session_id": session.session_id, field: r[field], "body": r} for r in rows],
            )
    return len(lifecycle), len(grouped)


def get_session(conn: Connection, session_id: UUID) -> ObservationSession:
    row = conn.execute(select(sessions).where(sessions.c.session_id == session_id)).mappings().one()
    if content_id(row["body"]) != row["body_hash"]:
        raise ValueError("SESSION_HASH_MISMATCH")
    return ObservationSession.model_validate(row["body"])
