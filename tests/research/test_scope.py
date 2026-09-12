"""Static boundary checks for the deliberately pure Phase 3.1 kernel."""

import ast
from pathlib import Path


def test_research_dependencies_and_capabilities_are_math_only() -> None:
    allowed = {
        "collections.abc",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "trading_ecosystem.datasets.contracts",
        "trading_ecosystem.domain.arithmetic",
        "trading_ecosystem.domain.primitives",
        "trading_ecosystem.research.indicators.core",
        "trading_ecosystem.research.indicators.observations",
        "trading_ecosystem.research.indicators.states",
    }
    forbidden_calls = {"open", "eval", "exec", "__import__", "float"}
    forbidden_names = {
        "backtest",
        "simulate",
        "position",
        "order",
        "fill",
        "sl",
        "tp",
        "pnl",
        "equity",
        "optimize",
        "grid_search",
        "walk_forward",
        "risk_sizing",
    }
    sources = list(Path("src/trading_ecosystem/research").rglob("*.py"))
    assert sources
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and node.module in allowed
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls
            if isinstance(node, ast.Constant):
                assert not isinstance(node.value, float)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Name)):
                name = node.id if isinstance(node, ast.Name) else node.name
                assert name.lower() not in forbidden_names
            if isinstance(node, ast.FunctionDef):
                if any(arg.arg in {"period", "lookback"} for arg in node.args.args):
                    assert not node.args.defaults


def test_phase3_verifier_does_not_load_historical_artifacts() -> None:
    source = Path("scripts/verify_phase3_1.ps1").read_text(encoding="utf-8")
    assert "datasets.verify" not in source
    assert "verify_phase2b.ps1" not in source
    assert "data/datasets" not in source
    assert "pytest" in source and "tests/research/test_scope.py" in source
