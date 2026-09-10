from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.config.settings import ConfigurationError


def create_database_engine(url: SecretStr) -> Engine:
    error = False
    engine = None
    try:
        parsed = make_url(url.get_secret_value())
        if parsed.drivername != "postgresql+psycopg" or not parsed.database:
            raise ValueError
        engine = create_engine(parsed, echo=False, hide_parameters=True, pool_pre_ping=True)
    except (ValueError, TypeError, SQLAlchemyError):
        error = True
    if error or engine is None:
        raise ConfigurationError("invalid database configuration")
    return engine
