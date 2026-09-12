"""Semantic identities independent of Decimal scale and runtime environment."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel

from trading_ecosystem.benchmarks.hashing import benchmark_definition_sha256
from trading_ecosystem.simulation.contracts import SimulationResult, SimulationSpec


def canonical_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return canonical_value(value.model_dump(mode="python"))
    if isinstance(value, Decimal):
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return "0" if value == 0 else text
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: canonical_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [canonical_value(item) for item in value]
    return value


def digest(value: object) -> str:
    content = (
        json.dumps(
            canonical_value(value),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def specification_sha256(spec: SimulationSpec) -> str:
    spec = SimulationSpec.model_validate(spec)
    return digest(
        {
            **spec.model_dump(mode="python", exclude={"benchmark", "bars"}),
            "benchmark_definition_sha256": benchmark_definition_sha256(spec.benchmark),
            "bar_fixture_sha256": digest(spec.bars),
            "arithmetic_version": "decimal34-half-even-v1",
        }
    )


def result_sha256(result: SimulationResult) -> str:
    return digest(SimulationResult.model_validate(result))
