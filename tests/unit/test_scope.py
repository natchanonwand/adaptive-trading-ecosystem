import ast
import subprocess
from pathlib import Path

from trading_ecosystem.domain.primitives import RuntimeMode


def test_no_execution_package_or_broker_write_implementation() -> None:
    # Phase 2A explicitly authorizes the optional SDK only inside discovery/sdk.py.
    # The Phase 1 domain remains SDK-free; the broader trading prohibition remains.
    prohibited_modules = {"mt5", "ccxt", "ib_insync", "alpaca", "fastapi"}
    prohibited_methods = {"order_send", "order_check", "send_order", "submit_order", "place_order"}
    for path in Path("src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "MetaTrader5" for alias in node.names):
                    assert path.as_posix() == "src/trading_ecosystem/discovery/sdk.py"
                assert all(
                    alias.name.split(".")[0] not in prohibited_modules for alias in node.names
                )
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] != "MetaTrader5"
                assert (node.module or "").split(".")[0] not in prohibited_modules
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in prohibited_methods
    lock = Path("uv.lock").read_text(encoding="utf-8").lower()
    for package in prohibited_modules:
        assert f'name = "{package.lower()}"' not in lock
    assert "LIVE" not in RuntimeMode.__members__


def test_sensitive_files_ignored_and_template_trackable() -> None:
    protected = [
        ".env",
        ".env.local",
        ".env.production",
        "private.key",
        "backup.dump",
        ".local/phase1-postgres/data/PG_VERSION",
        "pgpass.conf",
        "sample.sqlite3",
        "data/discovery/provider_identity.json",
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", *protected],
        capture_output=True,
        text=True,
        check=False,
    )
    assert set(result.stdout.splitlines()) == set(protected)
    assert (
        subprocess.run(
            ["git", "check-ignore", "--no-index", ".env.example"], capture_output=True
        ).returncode
        == 1
    )
