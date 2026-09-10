"""Explicit environment allowlist. No .env autoload or arbitrary interpolation."""

import os
from collections.abc import Mapping
from typing import Literal

from pydantic import SecretStr, ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from trading_ecosystem.domain.primitives import FrozenModel, RuntimeMode


class ConfigurationError(ValueError):
    pass


class Settings(FrozenModel):
    runtime_mode: RuntimeMode = RuntimeMode.RESEARCH
    entry_enabled: Literal[False] = False
    database_url: SecretStr | None = None


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    allowed = {"TE_RUNTIME_MODE", "TE_ENTRY_ENABLED", "TE_DATABASE_URL", "TE_TEST_DATABASE_URL"}
    error = False
    result: Settings | None = None
    try:
        if any(key.startswith("TE_") and key not in allowed for key in env):
            raise ValueError
        entry = env.get("TE_ENTRY_ENABLED", "false").lower()
        if entry not in {"", "false", "0"}:
            raise ValueError
        mode = RuntimeMode(env.get("TE_RUNTIME_MODE") or "RESEARCH")
        raw_url = env.get("TE_DATABASE_URL")
        secret = None
        if raw_url:
            parsed = make_url(raw_url)
            if parsed.drivername != "postgresql+psycopg" or not parsed.database:
                raise ValueError
            secret = SecretStr(raw_url)
        result = Settings(runtime_mode=mode, database_url=secret)
    except (ValueError, TypeError, ValidationError, SQLAlchemyError):
        error = True
    # Outside the except block: do not retain a secret-bearing exception context.
    if error or result is None:
        raise ConfigurationError("invalid application configuration")
    return result
