"""Accounting stays pure and the complete tracked baseline stays frozen."""

import ast
import subprocess
from pathlib import Path

from trading_ecosystem.domain.primitives import RuntimeMode


def test_accounting_scope() -> None:
    allowed = {
        "collections.abc",
        "enum",
        "typing",
        "pydantic",
        "datetime",
        "decimal",
        "uuid",
        "trading_ecosystem.domain.primitives",
        "trading_ecosystem.domain.arithmetic",
        "trading_ecosystem.domain.canonical",
        "trading_ecosystem.accounting.contracts",
        "trading_ecosystem.accounting.projection",
    }
    forbidden = {
        "order_send",
        "order_check",
        "submit",
        "amend_protection",
        "cancel",
        "connect",
        "socket",
        "urlopen",
        "request",
        "getenv",
        "environ",
        "open",
        "eval",
        "exec",
        "__import__",
        "getattr",
        "now",
        "today",
        "uuid4",
    }
    sources = list(Path("src/trading_ecosystem/accounting").glob("*.py"))
    assert {p.stem for p in sources} == {"__init__", "contracts", "projection", "performance"}
    for source in sources:
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(item.name in allowed for item in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and node.module in allowed
            if isinstance(node, ast.Constant):
                assert not isinstance(node.value, float)
                assert node.value != "LIVE"
            if isinstance(node, ast.Name):
                assert node.id not in forbidden
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden
    assert "LIVE" not in RuntimeMode.__members__


def test_entire_tracked_phase3_3c_baseline_unchanged() -> None:
    # Check every frozen path, including deletions; later authorized checkpoints
    # add tracked files and must not be confused with edits to frozen source.
    names = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "phase3.3c-v0.1.0"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.splitlines()
    assert names
    result = subprocess.run(
        ["git", "diff", "--exit-code", "phase3.3c-v0.1.0", "--", *names],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
