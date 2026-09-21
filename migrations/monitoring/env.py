"""Additive monitoring lineage; the frozen operational Alembic head stays unchanged."""

from alembic import context
from sqlalchemy import text

from trading_ecosystem.config.settings import ConfigurationError, load_settings
from trading_ecosystem.monitoring.schema import metadata
from trading_ecosystem.persistence.database import create_database_engine


def run_migrations() -> None:
    settings = load_settings()
    if settings.database_url is None:
        raise ConfigurationError("database configuration required for monitoring migrations")
    if context.is_offline_mode():
        context.configure(
            dialect_name="postgresql",
            target_metadata=metadata,
            literal_binds=True,
            version_table_schema="monitoring",
        )
        with context.begin_transaction():
            context.execute("CREATE SCHEMA IF NOT EXISTS monitoring")
            context.run_migrations()
        return
    engine = create_database_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            with connection.begin():
                current = connection.execute(
                    text("SELECT version_num FROM public.alembic_version")
                ).scalar_one()
                if current != "0001_journal":
                    raise ConfigurationError("frozen operational migration baseline required")
                connection.execute(text("CREATE SCHEMA IF NOT EXISTS monitoring"))
            context.configure(
                connection=connection,
                target_metadata=metadata,
                version_table_schema="monitoring",
                include_schemas=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
