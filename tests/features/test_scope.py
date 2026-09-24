import ast
from pathlib import Path


def test_offline_feature_domain_has_no_native_inference_or_execution_dependencies() -> None:
    forbidden = ("MetaTrader5", "openai", "anthropic", "torch", "tensorflow", "subprocess")
    for path in Path("src/trading_ecosystem/features").glob("*.py"):
        text = path.read_text()
        assert "order_" + "send" not in text and "order_check" not in text
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                assert all(not item.name.startswith(forbidden) for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(forbidden)
                assert module not in {
                    "trading_ecosystem.observer.native",
                    "trading_ecosystem.observer.runtime",
                }
