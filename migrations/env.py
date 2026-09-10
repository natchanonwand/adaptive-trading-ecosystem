"""Database URL is read from environment, never embedded in Alembic files."""

from alembic import context

from trading_ecosystem.config.settings import ConfigurationError, load_settings
from trading_ecosystem.persistence.database import create_database_engine
from trading_ecosystem.persistence.schema import metadata


def run_migrations() -> None:
    settings = load_settings()
    if settings.database_url is None:
        raise ConfigurationError("database configuration required for migrations")
    if context.is_offline_mode():
        context.configure(dialect_name="postgresql", target_metadata=metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_database_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
