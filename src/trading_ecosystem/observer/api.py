"""Read-only observer page API, alongside the unchanged dashboard and SSE APIs."""

from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy import Connection, Engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.dashboard_api.server import DashboardHandler, DashboardServer
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.observer.identity import instances
from trading_ecosystem.observer.store import episodes, events, get_session, load_frames, sessions
from trading_ecosystem.observer.summary import summarize


def view(conn: Connection, session_id: UUID | None) -> Record:
    listings = (
        conn.execute(select(sessions).order_by(sessions.c.session_id).limit(51)).mappings().all()
    )
    result: Record = {
        "sessions": [
            {"session": r["body"], "status": r["status"], "heartbeat": r["heartbeat"]}
            for r in listings[:50]
        ],
        "has_more_sessions": len(listings) > 50,
        "selected": None,
    }
    if session_id is None:
        return result
    session = get_session(conn, session_id)
    current = (
        conn.execute(select(sessions).where(sessions.c.session_id == session_id)).mappings().one()
    )
    episode_rows = list(
        conn.execute(
            select(episodes.c.body)
            .where(episodes.c.session_id == session_id)
            .order_by(episodes.c.episode_id)
            .limit(2000)
        ).scalars()
    )
    event_rows = list(
        conn.execute(
            select(events.c.body)
            .where(events.c.session_id == session_id)
            .order_by(events.c.body["sequence"].as_integer())
            .limit(20000)
        ).scalars()
    )
    total = conn.execute(
        select(func.count()).select_from(events).where(events.c.session_id == session_id)
    ).scalar_one()
    total_episodes = conn.execute(
        select(func.count()).select_from(episodes).where(episodes.c.session_id == session_id)
    ).scalar_one()
    retained = load_frames(conn, session)
    result["selected"] = {
        "session": session.model_dump(mode="json"),
        "status": current["status"],
        "heartbeat": current["heartbeat"],
        "summary": summarize(episode_rows, event_rows),
        "metrics_complete": total <= 20000 and total_episodes <= 2000,
        "observed_events": total,
        "observed_deals": sum(e["kind"] == "DEAL_OBSERVED" for e in event_rows),
        "positions": list(retained[-1].positions) if retained else [],
        "activity": event_rows[-50:],
        "episodes": episode_rows[:100],
        "source": "EXTERNAL_OBSERVER",
        "source_instances": instances(session, event_rows),
        "read_only": True,
    }
    return result


class ObserverServer(DashboardServer):
    def __init__(self, engine: Engine, port: int = 8765) -> None:
        super().__init__(engine, port)
        self.RequestHandlerClass = ObserverHandler


class ObserverHandler(DashboardHandler):
    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path != "/api/v1/observer":
            super().do_GET()
            return
        if self.headers.get("Origin") is not None or self.headers.get("Host") not in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }:
            self._json(403, {"error": "LOCAL_CLIENT_REQUIRED"})
            return
        try:
            args = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
            if set(args) - {"session_id"} or any(len(v) != 1 for v in args.values()):
                raise ValueError
            session_id = UUID(args["session_id"][0]) if "session_id" in args else None
        except ValueError:
            self._json(400, {"error": "INVALID_QUERY"})
            return
        try:
            with self.server.engine.connect() as conn:
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                response = view(conn, session_id)
            self._json(200, response)
        except (ValueError, SQLAlchemyError, RuntimeError):
            self._json(503, {"error": "OBSERVER_DATA_UNAVAILABLE"})
