"""Additive research metadata schema using the existing Alembic/database conventions."""

from alembic import context
from sqlalchemy import text

from trading_ecosystem.config.settings import ConfigurationError, load_settings
from trading_ecosystem.persistence.database import create_database_engine
from trading_ecosystem.workbench.store import metadata


def run_migrations() -> None:
    settings = load_settings()
    if settings.database_url is None:
        raise ConfigurationError("workbench database configuration required")
    if context.is_offline_mode():
        context.configure(
            dialect_name="postgresql",
            target_metadata=metadata,
            literal_binds=True,
            version_table_schema="workbench",
        )
        with context.begin_transaction():
            context.execute("CREATE SCHEMA IF NOT EXISTS workbench")
            context.run_migrations()
        return
    engine = create_database_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            with connection.begin():
                if (
                    connection.execute(
                        text("SELECT version_num FROM public.alembic_version")
                    ).scalar_one()
                    != "0001_journal"
                ):
                    raise ConfigurationError("frozen operational baseline required")
                connection.execute(text("CREATE SCHEMA IF NOT EXISTS workbench"))
            context.configure(
                connection=connection,
                target_metadata=metadata,
                version_table_schema="workbench",
                include_schemas=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
