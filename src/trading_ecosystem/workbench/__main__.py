"""Operator startup of the local Workbench; all onboarding happens in the browser."""

import argparse
from pathlib import Path

from trading_ecosystem.config.settings import load_settings
from trading_ecosystem.persistence.database import create_database_engine
from trading_ecosystem.workbench.api import WorkbenchServer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8785)
    args = parser.parse_args()
    settings = load_settings()
    if settings.database_url is None or not 1024 <= args.port <= 65535:
        raise ValueError("LOCAL_DATABASE_AND_VALID_PORT_REQUIRED")
    engine = create_database_engine(settings.database_url)
    try:
        with WorkbenchServer(
            engine, Path(".local/artifacts/research_projects"), Path("dashboard/dist"), args.port
        ) as server:
            print(
                f"Research Workbench: http://127.0.0.1:{server.server_port}/workbench", flush=True
            )
            server.serve_forever()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
