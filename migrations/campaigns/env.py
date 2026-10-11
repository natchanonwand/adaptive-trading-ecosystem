"""Additive campaign schema; frozen Phase 5B migration lineage is unchanged."""

from alembic import context
from sqlalchemy import text

from trading_ecosystem.config.settings import load_settings
from trading_ecosystem.persistence.database import create_database_engine

settings = load_settings()
if settings.database_url is None:
    raise ValueError("CAMPAIGN_DATABASE_REQUIRED")
engine = create_database_engine(settings.database_url)
try:
    with engine.connect() as conn:
        with conn.begin():
            if (
                conn.execute(
                    text("SELECT version_num FROM workbench.baseline_alembic_version")
                ).scalar_one()
                != "0004_experiment_definitions"
            ):
                raise ValueError("FROZEN_CONTRACT_SCHEMA_REQUIRED")
        context.configure(
            connection=conn,
            version_table_schema="workbench",
            version_table="campaign_alembic_version",
        )
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
