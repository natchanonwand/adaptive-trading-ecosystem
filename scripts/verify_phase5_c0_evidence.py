"""Read-only Phase 5B database/publication preservation; no real experiments are created."""

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select, text

from trading_ecosystem.tester import publication, readiness, store
from trading_ecosystem.workbench import store as onboarding

EXPECTED_PUBLICATION = (
    "e1d01c152831d1fe7f3a0b9736339cba0e961dbcd7130ea7d57967c6f13a5cf2"  # pragma: allowlist secret
)


def main() -> None:
    url = json.loads(Path(".local/phase4_a/runtime.json").read_text(encoding="utf-8-sig"))[
        "database_url"
    ]
    tables = [
        onboarding.projects,
        onboarding.candidates,
        onboarding.artifacts,
        readiness.authorizations,
        readiness.configurations,
        store.runs,
        store.results,
        publication.publications,
    ]
    engine = create_engine(url, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as conn:
            rows = {
                t.name: [dict(v) for v in conn.execute(select(t).order_by(t.c.id)).mappings()]
                for t in tables
            }
            if rows != json.loads(Path(".local/phase5_c0/database-before.json").read_bytes()):
                raise ValueError("PHASE5B_HISTORY_CHANGED")
            record = publication.read(conn, UUID("aebb719c-6738-4b1a-a323-3f405ed512fe"))
            if record is None or record["identity"] != EXPECTED_PUBLICATION:
                raise ValueError("PUBLICATION_CHANGED")
            for table in ("experiment_definitions", "experiment_protocol_events"):
                if conn.execute(
                    text("SELECT to_regclass(:name)"), {"name": "workbench." + table}
                ).scalar_one():
                    if (
                        conn.execute(text("SELECT count(*) FROM workbench." + table)).scalar_one()
                        != 0
                    ):
                        raise ValueError("UNAUTHORIZED_REAL_EXPERIMENT_RECORDS")
    finally:
        engine.dispose()
    print(
        "PASS: eight Phase 5B tables unchanged; 3 BaselineRuns, 0 BaselineResults, "
        "1 publication; no real experiment records"
    )


if __name__ == "__main__":
    main()
