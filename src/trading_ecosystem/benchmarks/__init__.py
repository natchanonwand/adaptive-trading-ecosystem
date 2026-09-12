"""Four immutable exploratory benchmark hypotheses; no empirical results."""

from trading_ecosystem.benchmarks.contracts import (
    BenchmarkDefinition,
    BenchmarkId,
    BenchmarkRegistry,
    EvaluationInput,
    ResearchDecision,
    ResearchObservation,
)
from trading_ecosystem.benchmarks.registry import REGISTRY, get_definition
from trading_ecosystem.benchmarks.rules import evaluate

__all__ = [
    "REGISTRY",
    "BenchmarkDefinition",
    "BenchmarkId",
    "BenchmarkRegistry",
    "EvaluationInput",
    "ResearchDecision",
    "ResearchObservation",
    "evaluate",
    "get_definition",
]
