"""Production boundaries forbid strategy recomputation and broker integration."""

import ast
import subprocess
from pathlib import Path


def test_portfolio_scope_and_frozen_baseline() -> None:
    permitted = {
        "datetime",
        "decimal",
        "typing",
        "pathlib",
        "argparse",
        "pydantic",
        "trading_ecosystem.benchmarks.contracts",
        "trading_ecosystem.benchmarks.hashing",
        "trading_ecosystem.benchmarks.registry",
        "trading_ecosystem.domain.primitives",
        "trading_ecosystem.domain.arithmetic",
        "trading_ecosystem.datasets.contracts",
        "trading_ecosystem.datasets.storage",
        "trading_ecosystem.backtests.evidence",
        "trading_ecosystem.backtests.metrics",
        "trading_ecosystem.simulation.contracts",
        "trading_ecosystem.simulation.hashing",
    }
    permitted |= {
        "trading_ecosystem.portfolios." + name
        for name in ["contracts", "events", "accounting", "synthetic", "evidence", "report"]
    }
    sources = list(Path("src/trading_ecosystem/portfolios").glob("*.py"))
    assert len(sources) == 8
    for path in sources:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(item.name in permitted for item in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and node.module in permitted
            if isinstance(node, ast.Constant):
                assert not isinstance(node.value, float)
    checked = subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            "phase3.3b-v0.1.0",
            "--",
            "src/trading_ecosystem/backtests",
            "src/trading_ecosystem/benchmarks",
            "src/trading_ecosystem/simulation",
            "src/trading_ecosystem/research",
            "src/trading_ecosystem/datasets",
            "PHASE3_3B_REPORT.md",
        ],
        capture_output=True,
        check=False,
    )
    assert checked.returncode == 0


def test_generated_portfolio_evidence_ignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "data/research/phase3_3c/synthetic/result.json"],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
