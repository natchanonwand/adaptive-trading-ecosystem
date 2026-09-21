"""Start the read-only local API with additive dashboard queries."""

import argparse

from trading_ecosystem.config.settings import load_settings
from trading_ecosystem.dashboard_api.server import DashboardServer
from trading_ecosystem.persistence.database import create_database_engine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    settings = load_settings()
    if settings.database_url is None:
        parser.error("TE_DATABASE_URL is required")
    assert settings.database_url is not None
    engine = create_database_engine(settings.database_url)
    with DashboardServer(engine, args.port) as server:
        try:
            print(f"Read-only dashboard API: http://127.0.0.1:{server.server_port}", flush=True)
            server.serve_forever()
        except KeyboardInterrupt:
            server.stopping.set()
        finally:
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
