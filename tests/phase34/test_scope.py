import ast
import subprocess
from pathlib import Path


def test_domain_import_allowlist_and_no_authority() -> None:
    allowed = {
        "datetime",
        "decimal",
        "typing",
        "pydantic",
        "trading_ecosystem.accounting.contracts",
        "trading_ecosystem.accounting.performance",
        "trading_ecosystem.accounting.projection",
        "trading_ecosystem.domain.arithmetic",
        "trading_ecosystem.domain.primitives",
        "trading_ecosystem.portfolio.contracts",
        "trading_ecosystem.portfolio.projection",
        "trading_ecosystem.risk.contracts",
    }
    forbidden = {
        "order_send",
        "order_check",
        "connect",
        "submit",
        "open",
        "exec",
        "eval",
        "__import__",
        "getattr",
        "now",
        "today",
        "uuid4",
        "total_seconds",
    }
    sources = [
        *Path("src/trading_ecosystem/portfolio").glob("*.py"),
        *Path("src/trading_ecosystem/risk").glob("*.py"),
    ]
    assert len(sources) == 7
    for path in sources:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(n.name in allowed for n in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and node.module in allowed
            if isinstance(node, ast.Constant):
                assert not isinstance(node.value, float)
                assert node.value != "LIVE"
            if isinstance(node, ast.Name):
                assert node.id not in forbidden
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden


def test_all_frozen_tracked_files_unchanged() -> None:
    names = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "phase3.3c-v0.1.0"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    checked = subprocess.run(
        ["git", "diff", "--exit-code", "phase3.3c-v0.1.0", "--", *names],
        check=False,
        capture_output=True,
    )
    assert checked.returncode == 0
