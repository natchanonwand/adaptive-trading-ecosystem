import io
import logging
import traceback

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.engine import URL

from trading_ecosystem.config.redaction import RedactingFilter
from trading_ecosystem.config.settings import ConfigurationError, Settings, load_settings
from trading_ecosystem.domain.primitives import Asset, RuntimeMode
from trading_ecosystem.domain.safety import DisabledEntryPermission


def test_config_defaults_and_immutable() -> None:
    settings = load_settings({})
    assert settings.entry_enabled is False
    assert settings.runtime_mode is RuntimeMode.RESEARCH
    assert settings.database_url is None
    with pytest.raises(ValidationError):
        settings.entry_enabled = True  # type: ignore[assignment, misc]
    with pytest.raises(ValidationError):
        Settings.model_validate({"entry_enabled": True})


@pytest.mark.parametrize(
    "env",
    [
        {"TE_RUNTIME_MODE": "LIVE"},
        {"TE_ENTRY_ENABLED": "true"},
        {"TE_LIVE_ENABLED": "true"},
        {"TE_RUNTIME_MODE": "invalid"},
    ],
)
def test_env_cannot_enable_live_or_entries(env: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError):
        load_settings(env)


def test_all_modes_and_assets_are_entry_disabled() -> None:
    guard = DisabledEntryPermission()
    for mode in RuntimeMode:
        for asset in Asset:
            assert guard.can_open_new_entry(asset=asset, mode=mode).enabled is False


def test_secret_boundaries_and_redacted_logs() -> None:
    # Synthetic, generated test value; never a real credential or a snapshot.
    sensitive = "synthetic-" + "configuration-marker"
    secret = SecretStr(sensitive)
    settings = Settings(database_url=secret)
    assert sensitive not in repr(settings)
    assert sensitive not in settings.model_dump_json()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    redactor = RedactingFilter([secret])
    handler.addFilter(redactor)
    logger = logging.Logger("isolated-test")
    logger.addHandler(handler)
    logger.warning("received %s", sensitive)
    try:
        raise ValueError(sensitive)
    except ValueError:
        logger.exception("failed")
    logger.warning("password=%s", sensitive)
    assert sensitive not in stream.getvalue()
    assert "REDACTED" in stream.getvalue()
    assert sensitive not in repr(redactor)
    with pytest.raises(ConfigurationError) as error:
        load_settings({"TE_DATABASE_URL": sensitive})
    assert sensitive not in "".join(traceback.format_exception(error.value))
    assert error.value.__context__ is None


def test_configured_url_password_fragment_is_redacted() -> None:
    sensitive = "synthetic-" + "password-fragment"
    url = URL.create("postgresql+psycopg", username="test", password=sensitive, database="test")
    config = load_settings({"TE_DATABASE_URL": url.render_as_string(hide_password=False)})
    assert config.database_url is not None
    redactor = RedactingFilter([config.database_url])
    record = logging.LogRecord("test", logging.WARNING, "", 1, "fragment %s", (sensitive,), None)
    assert redactor.filter(record)
    assert sensitive not in record.getMessage()
