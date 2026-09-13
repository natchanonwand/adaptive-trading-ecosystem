"""Production dependency whitelist and ignored evidence checks."""

import ast
import subprocess
from pathlib import Path


def test_production_scope() -> None:
    allowed = {
        "argparse",
        "re",
        "json",
        "pathlib",
        "decimal",
        "typing",
        "enum",
        "trading_ecosystem.backtests.contracts",
        "trading_ecosystem.backtests.datasets",
        "trading_ecosystem.backtests.evidence",
        "trading_ecosystem.backtests.metrics",
        "trading_ecosystem.backtests.runner",
        "trading_ecosystem.backtests.signals",
        "trading_ecosystem.benchmarks.contracts",
        "trading_ecosystem.benchmarks.hashing",
        "trading_ecosystem.benchmarks.registry",
        "trading_ecosystem.benchmarks.rules",
        "trading_ecosystem.datasets.contracts",
        "trading_ecosystem.datasets.storage",
        "trading_ecosystem.domain.primitives",
        "trading_ecosystem.domain.arithmetic",
        "trading_ecosystem.research",
        "trading_ecosystem.research.indicators",
        "trading_ecosystem.research.indicators.observations",
        "trading_ecosystem.simulation",
        "trading_ecosystem.simulation.contracts",
        "trading_ecosystem.simulation.execution",
        "trading_ecosystem.simulation.hashing",
    }
    forbidden = {
        "order_send",
        "order_check",
        "TradeRequest",
        "optimize",
        "grid_search",
        "random_search",
        "walk_forward",
        "portfolio",
        "machine_learning",
        "news",
        "llm",
        "ema",
        "sma",
        "wilder_atr",
        "previous_high",
        "previous_low",
        "trailing_return",
    }
    paths = list(Path("src/trading_ecosystem/backtests").glob("*.py"))
    assert len(paths) == 8
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(item.name in allowed for item in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and node.module in allowed
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                assert node.name not in forbidden
            if isinstance(node, ast.Constant):
                assert not isinstance(node.value, float)


def test_evidence_ignored_and_frozen_sources_unchanged() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "data/research/phase3_3b/synthetic/result.json"],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    result = subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            "phase3.3a-v0.1.0",
            "--",
            "src/trading_ecosystem/benchmarks",
            "src/trading_ecosystem/simulation",
            "src/trading_ecosystem/research",
            "src/trading_ecosystem/datasets",
            "research/benchmark_registry_v0.1.0.json",
            "PHASE2B_REPORT.md",
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
