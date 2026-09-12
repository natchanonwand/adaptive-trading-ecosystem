"""Production AST boundaries, excluding explanatory documentation."""

import ast
from pathlib import Path


def test_simulation_production_dependencies_and_scope() -> None:
    allowed = {
        "datetime",
        "decimal",
        "enum",
        "typing",
        "pydantic",
        "hashlib",
        "json",
        "trading_ecosystem.benchmarks.contracts",
        "trading_ecosystem.benchmarks.hashing",
        "trading_ecosystem.domain.primitives",
        "trading_ecosystem.domain.arithmetic",
        "trading_ecosystem.simulation.contracts",
        "trading_ecosystem.simulation.execution",
        "trading_ecosystem.simulation.lifecycle",
        "trading_ecosystem.simulation.events",
        "trading_ecosystem.simulation.hashing",
    }
    forbidden = {
        "order_send",
        "order_check",
        "TradeRequest",
        "open",
        "eval",
        "exec",
        "__import__",
        "float",
        "portfolio",
        "optimize",
        "grid_search",
        "walk_forward",
        "news",
        "llm",
        "random_search",
        "machine_learning",
        "risk_sizing",
        "equity",
        "drawdown",
    }
    paths = list(Path("src/trading_ecosystem/simulation").glob("*.py"))
    assert len(paths) == 6
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and node.module in allowed
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                assert node.name not in forbidden
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                assert name not in forbidden | {
                    "read_bytes",
                    "read_text",
                    "write_bytes",
                    "write_text",
                }
            if isinstance(node, ast.Constant):
                assert not isinstance(node.value, float)


def test_fast_verification_excludes_real_datasets() -> None:
    text = Path("scripts/verify_phase3_3a.ps1").read_text(encoding="utf-8")
    assert "tests/simulation/test_scope.py" in text
    assert "pytest" in text
    for prohibited in ("datasets.verify", "verify_phase2b.ps1", "data/datasets", "MetaTrader5"):
        assert prohibited not in text
