"""Independent additive lineage following existing multi-schema migration conventions."""

from alembic import context
from sqlalchemy import text

from trading_ecosystem.config.settings import ConfigurationError, load_settings
from trading_ecosystem.persistence.database import create_database_engine


def migrate() -> None:
    settings = load_settings()
    if settings.database_url is None:
        raise ConfigurationError("BASELINE_DATABASE_REQUIRED")
    engine = create_database_engine(settings.database_url)
    try:
        with engine.connect() as conn:
            with conn.begin():
                if (
                    conn.execute(
                        text("SELECT version_num FROM workbench.alembic_version")
                    ).scalar_one()
                    != "0001_projects"
                ):
                    raise ConfigurationError("FROZEN_WORKBENCH_SCHEMA_REQUIRED")
            context.configure(
                connection=conn,
                version_table_schema="workbench",
                version_table="baseline_alembic_version",
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


migrate()
