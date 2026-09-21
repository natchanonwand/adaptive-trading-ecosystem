"""Monitoring is an observer; the existing domain authority stays independent."""

import ast
from pathlib import Path

from trading_ecosystem.domain.primitives import RuntimeMode


def test_monitoring_has_no_execution_or_external_service_dependency() -> None:
    forbidden = {
        "MetaTrader5",
        "openai",
        "fastapi",
        "redis",
        "kafka",
        "trading_ecosystem.execution",
        "trading_ecosystem.brokers",
    }
    forbidden_calls = {"order_send", "order_check", "evaluate_and_reserve", "apply_fill"}
    for path in Path("src/trading_ecosystem/monitoring").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(not any(n.name.startswith(f) for f in forbidden) for n in node.names)
            if isinstance(node, ast.ImportFrom):
                assert not any((node.module or "").startswith(f) for f in forbidden)
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                )
                assert name not in forbidden_calls
    assert "LIVE" not in RuntimeMode.__members__


def test_adapters_only_copy_financial_values() -> None:
    path = Path("src/trading_ecosystem/monitoring/adapters.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # Union type annotations are allowed; arithmetic is confined to the original domain.
    assert not any(
        isinstance(n, ast.BinOp) and not isinstance(n.op, ast.BitOr) for n in ast.walk(tree)
    )
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in {"sum", "min", "max", "round"}
        for n in ast.walk(tree)
    )
