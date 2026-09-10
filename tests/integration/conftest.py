import os
import re
import subprocess
import sys
from collections.abc import Iterator
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from trading_ecosystem.persistence.database import create_database_engine


@pytest.fixture(scope="session")
def database() -> Iterator[Engine]:
    raw = os.environ.get("TE_TEST_DATABASE_URL")
    if not raw:
        pytest.fail("TE_TEST_DATABASE_URL required; integration tests must not silently skip")
    admin_url = make_url(raw)
    # Only explicitly disposable, local test infrastructure can create/drop fixtures.
    if admin_url.host not in {"127.0.0.1", "localhost"} or admin_url.database != "postgres":
        pytest.fail("test administrator URL must target local postgres maintenance database")
    name = "phase1_test_" + uuid4().hex
    assert re.fullmatch(r"phase1_test_[0-9a-f]{32}", name)
    admin = create_database_engine(SecretStr(raw))
    target = admin_url.set(database=name)
    engine = create_database_engine(SecretStr(target.render_as_string(hide_password=False)))
    created = False
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        environment = dict(os.environ)
        environment["TE_DATABASE_URL"] = target.render_as_string(hide_password=False)
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=environment,
            capture_output=True,
            check=False,
        )
        if migration.returncode != 0:
            pytest.fail("fresh Alembic upgrade failed; driver output suppressed for secret safety")
        yield engine
    finally:
        engine.dispose()
        if created:
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()
