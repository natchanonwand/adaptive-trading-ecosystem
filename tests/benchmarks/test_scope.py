"""Production-only dependency and capability boundaries for Phase 3.2."""

import ast
from pathlib import Path


def test_benchmark_production_scope() -> None:
    allowed = {
        "collections.abc",
        "enum",
        "typing",
        "pydantic",
        "pathlib",
        "json",
        "hashlib",
        "trading_ecosystem.domain.primitives",
        "trading_ecosystem.benchmarks.contracts",
        "trading_ecosystem.benchmarks.registry",
        "trading_ecosystem.benchmarks.rules",
        "trading_ecosystem.research.indicators",
    }
    forbidden = {
        "open",
        "eval",
        "exec",
        "__import__",
        "float",
        "order_send",
        "order_check",
        "TradeRequest",
        "backtest",
        "simulate",
        "fill",
        "portfolio",
        "pnl",
        "equity",
        "drawdown",
        "optimize",
        "grid_search",
        "parameter_sweep",
        "random_search",
        "walk_forward",
        "machine_learning",
        "news",
        "llm",
        "trailing_return",
        "ema",
        "sma",
        "wilder_atr",
        "true_range",
        "previous_high",
        "previous_low",
    }
    sources = list(Path("src/trading_ecosystem/benchmarks").glob("*.py"))
    assert len(sources) == 5
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and node.module in allowed
                assert all(alias.name not in forbidden for alias in node.names)
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                )
                assert name not in forbidden
                assert name not in {"write_text", "write_bytes", "unlink", "mkdir"}
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                assert node.name not in forbidden
            if isinstance(node, ast.Constant):
                assert not isinstance(node.value, float)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assert node.target.id not in {"min", "max", "step", "candidate_values"}


def test_verifier_uses_synthetic_gate_only() -> None:
    source = Path("scripts/verify_phase3_2.ps1").read_text(encoding="utf-8")
    for forbidden in ("datasets.verify", "verify_phase2b.ps1", "data/datasets", "MetaTrader5"):
        assert forbidden not in source
    assert "pytest" in source and "tests/benchmarks/test_scope.py" in source
    assert "trading_ecosystem.benchmarks.hashing" in source
