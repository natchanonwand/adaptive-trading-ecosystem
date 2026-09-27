"""Read-only authorized candidate inventory. This script NEVER starts an EA."""

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from trading_ecosystem.config.settings import load_settings
from trading_ecosystem.persistence.database import create_database_engine
from trading_ecosystem.tester.evidence import write_json
from trading_ecosystem.workbench import store
from trading_ecosystem.workbench.contracts import Project


def main() -> None:
    settings = load_settings()
    if settings.database_url is None:
        raise ValueError("LOCAL_APPLICATION_DATABASE_REQUIRED")
    engine = create_database_engine(settings.database_url)
    eligible: list[str] = []
    projects = 0
    try:
        with engine.connect() as conn:
            for body in conn.execute(select(store.projects.c.body)).scalars():
                projects += 1
                project = Project.model_validate(body)
                candidate = store.get_candidate(conn, project.candidate_id)
                if (
                    project.broker_binding.ready()
                    and candidate.license_status == "USER_ATTESTED"
                    and candidate.tester_access_status == "USER_CONFIRMED"
                    and candidate.artifact_id
                ):
                    artifact = store.get_artifact(conn, candidate.artifact_id)
                    if store.verify_artifact(Path(".local/artifacts/research_projects"), artifact):
                        eligible.append(str(project.project_id))
    finally:
        engine.dispose()
    observed = datetime.now(UTC)
    evidence = dict(
        observed_at=observed.isoformat(),
        project_count=projects,
        authorized_candidate_count=len(eligible),
        eligible_project_ids=eligible,
        status="AUTHORIZED_CANDIDATE_REQUIRES_CONTROLLED_ACCEPTANCE"
        if eligible
        else "BLOCKED_NO_AUTHORIZED_CANDIDATE",
        mt5_execution_started=False,
    )
    path = Path(".local/phase5_b") / f"acceptance-readiness-{observed:%Y%m%dT%H%M%S%fZ}.json"
    write_json(path, evidence)
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
