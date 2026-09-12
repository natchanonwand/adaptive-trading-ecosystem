"""Versioned UTF-8 JSON identities and a source-configuration artifact verifier."""

import hashlib
import json
from pathlib import Path
from typing import Any

from trading_ecosystem.benchmarks.contracts import BenchmarkDefinition, BenchmarkRegistry
from trading_ecosystem.benchmarks.registry import REGISTRY

ARTIFACT_PATH = Path("research/benchmark_registry_v0.1.0.json")


def canonical_bytes(content: object) -> bytes:
    return (
        json.dumps(content, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")


def content_sha256(content: object) -> str:
    return hashlib.sha256(canonical_bytes(content)).hexdigest()


def definition_content(definition: BenchmarkDefinition) -> dict[str, Any]:
    checked = BenchmarkDefinition.model_validate(definition)
    return checked.model_dump(mode="json")


def benchmark_definition_sha256(definition: BenchmarkDefinition) -> str:
    return content_sha256(definition_content(definition))


def registry_content(registry: BenchmarkRegistry) -> dict[str, Any]:
    checked = BenchmarkRegistry.model_validate(registry)
    content = checked.model_dump(mode="json", exclude={"definitions"})
    content["definitions"] = [
        {
            **definition_content(item),
            "benchmark_definition_sha256": benchmark_definition_sha256(item),
        }
        for item in checked.definitions
    ]
    return content


def registry_sha256(registry: BenchmarkRegistry = REGISTRY) -> str:
    return content_sha256(registry_content(registry))


def artifact_content(registry: BenchmarkRegistry = REGISTRY) -> dict[str, Any]:
    return {**registry_content(registry), "registry_sha256": registry_sha256(registry)}


def verify_artifact(path: Path = ARTIFACT_PATH) -> None:
    # Exact canonical bytes also reject duplicate JSON keys and noncanonical encodings.
    if path.read_bytes() != canonical_bytes(artifact_content()):
        raise ValueError("REGISTRY_ARTIFACT_DIVERGENCE")


def main() -> int:
    verify_artifact()
    for item in REGISTRY.definitions:
        print(f"{item.benchmark_id.value}: {benchmark_definition_sha256(item)}")
    print(f"registry_sha256: {registry_sha256()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
