"""Explicit local monitoring server. Database ingestion remains a Python journal API."""

import argparse

from trading_ecosystem.config.settings import load_settings
from trading_ecosystem.monitoring.api import MonitoringServer
from trading_ecosystem.persistence.database import create_database_engine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    settings = load_settings()
    if settings.database_url is None:
        parser.error("TE_DATABASE_URL is required; use a local development database")
    assert settings.database_url is not None
    engine = create_database_engine(settings.database_url)
    server = MonitoringServer(engine, args.port)
    try:
        print(f"Read-only monitoring: http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stopping.set()
        server.server_close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
