import hashlib
import json
import runpy
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from trading_ecosystem.benchmarks import (
    REGISTRY,
    BenchmarkDefinition,
    BenchmarkId,
    BenchmarkRegistry,
)
from trading_ecosystem.benchmarks.hashing import (
    ARTIFACT_PATH,
    artifact_content,
    benchmark_definition_sha256,
    canonical_bytes,
    content_sha256,
    definition_content,
    registry_content,
    registry_sha256,
    verify_artifact,
)

verified_registry_digest = runpy.run_path("scripts/secret_scan.py")["verified_registry_digest"]


def test_exact_registry_ids_order_and_pinned_definitions() -> None:
    assert [item.benchmark_id.value for item in REGISTRY.definitions] == [
        "B01_LEGACY_HYBRID_V0",
        "B02_EMA_TREND_50_200",
        "B03_CHANNEL_20_10",
        "B04_CHANNEL_55_20",
    ]
    assert [
        (
            item.entry_rule.fast_ema_period,
            item.entry_rule.slow_ema_period,
            item.entry_rule.previous_high_period,
            item.exit_rule.previous_low_period,
            item.required_observations,
        )
        for item in REGISTRY.definitions
    ] == [
        (50, 200, 20, None, 250),
        (50, 200, None, None, 201),
        (None, None, 20, 10, 21),
        (None, None, 55, 20, 56),
    ]


@pytest.mark.parametrize("indices", [(0, 1, 2), (0, 1, 2, 3, 3), (0, 1, 2, 2), (1, 0, 2, 3)])
def test_registry_rejects_missing_fifth_duplicate_and_reordered(indices: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError):
        BenchmarkRegistry(definitions=tuple(REGISTRY.definitions[i] for i in indices))


@pytest.mark.parametrize("index", range(4))
def test_immutable_definitions_and_common_invariants(index: int) -> None:
    item = REGISTRY.definitions[index]
    assert item.direction == "LONG_ONLY" and item.time_basis == "H1_OBSERVED_BAR"
    assert item.research_status == "PREREGISTERED_EXPLORATORY_BENCHMARK"
    assert item.research_classification == "EXPLORATORY_RESEARCH_ONLY"
    for field in (
        "qualification_eligible",
        "profitability_known",
        "optimized",
        "literature_replication",
        "pyramiding",
        "averaging_down",
        "short_support",
        "same_bar_reentry",
        "trailing_stop",
    ):
        assert getattr(item, field) is False
        with pytest.raises(ValidationError):
            item.model_copy(update={field: True})
    with pytest.raises(ValidationError):
        item.required_observations = 1  # type: ignore[misc]
    with pytest.raises(ValidationError):
        item.entry_rule.previous_high_period = 1  # type: ignore[misc]
    with pytest.raises(TypeError):
        BenchmarkDefinition.model_construct(**item.model_dump())
    assert item.model_copy(deep=True) == item
    assert item.protective_stop.atr_period == 14 and item.protective_stop.atr_multiple == 2
    assert item.protective_stop.atr_type == "WILDER" and item.protective_stop.fixed_after_entry
    assert item.decision_timing.decision_time == "BAR_CLOSE_TIME"
    assert item.decision_timing.future_execution == "STRICTLY_AFTER_DECISION_TIME"
    assert item.decision_timing.same_close_fill_allowed is False


def test_b01_actual_entry_tp_dependency_and_no_other_tp() -> None:
    first = REGISTRY.definitions[0]
    assert first.origin_category == "PROJECT_LEGACY_HYPOTHESIS"
    assert first.take_profit.kind == "FIXED_PRICE_R_MULTIPLE" and first.take_profit.r_multiple == 2
    assert (
        first.take_profit.initial_price_risk_basis == "ACTUAL_SIMULATED_ENTRY_FILL_MINUS_FIXED_STOP"
    )
    assert (
        first.take_profit.target_basis
        == "ACTUAL_SIMULATED_ENTRY_FILL_PLUS_R_MULTIPLE_OF_INITIAL_PRICE_RISK"
    )
    assert first.exit_rule.normal_exits == ("STOP_LOSS", "TAKE_PROFIT")
    for item in REGISTRY.definitions[1:]:
        assert item.take_profit.kind == "NONE" and item.take_profit.r_multiple is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("benchmark_id", "B05_TSMOM"),
        ("family", "UNKNOWN"),
        ("direction", "SHORT_ONLY"),
        ("time_basis", "DAILY"),
        ("origin_category", "EXACT_TURTLE_REPLICATION"),
        ("required_observations", 251),
        ("created_at", "2024-01-01"),
        ("machine_path", "synthetic/path"),
        ("schema_version", "unversioned"),
    ],
)
def test_malformed_or_unapproved_definition_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        REGISTRY.definitions[0].model_copy(update={field: value})


def test_parameters_cannot_be_changed_under_registered_id() -> None:
    item = REGISTRY.definitions[1]
    changed = item.entry_rule.model_copy(update={"fast_ema_period": 40})
    with pytest.raises(ValidationError):
        item.model_copy(update={"entry_rule": changed})


def test_stable_hashes_all_semantics_and_explicit_definition_hashes() -> None:
    for item in REGISTRY.definitions:
        raw = definition_content(item)
        expected = hashlib.sha256(
            (json.dumps(raw, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        ).hexdigest()
        assert benchmark_definition_sha256(item) == expected
        restored = BenchmarkDefinition.model_validate(json.loads(json.dumps(raw)))
        assert benchmark_definition_sha256(restored) == expected
        assert content_sha256(dict(reversed(list(raw.items())))) == expected
        # A semantic alteration changes identity, and cannot masquerade as an approved definition.
        changed = {**raw, "required_observations": raw["required_observations"] + 1}
        assert content_sha256(changed) != expected
        with pytest.raises(ValidationError):
            BenchmarkDefinition.model_validate(changed)
    content = registry_content(REGISTRY)
    assert registry_sha256() == content_sha256(content) == registry_sha256(REGISTRY.model_copy())
    assert [entry["benchmark_definition_sha256"] for entry in content["definitions"]] == [
        benchmark_definition_sha256(item) for item in REGISTRY.definitions
    ]
    changed_registry = {**content, "definitions": list(reversed(content["definitions"]))}
    assert content_sha256(changed_registry) != registry_sha256()


def test_runtime_environment_does_not_participate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = registry_sha256()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPUTERNAME", "synthetic-other-machine")
    assert registry_sha256() == before
    with pytest.raises(ValidationError):
        REGISTRY.model_copy(update={"created_at": "2024-01-01T00:00:00Z"})


def test_artifact_exact_bytes_and_tampering(tmp_path: Path) -> None:
    verify_artifact()
    assert ARTIFACT_PATH.read_bytes() == canonical_bytes(artifact_content())
    altered = artifact_content()
    altered["definitions"][0]["entry_rule"]["previous_high_period"] = 21
    path = tmp_path / "registry.json"
    path.write_bytes(canonical_bytes(altered))
    with pytest.raises(ValueError, match="REGISTRY_ARTIFACT_DIVERGENCE"):
        verify_artifact(path)
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", str(ARTIFACT_PATH)], capture_output=True, check=False
    )
    assert result.returncode == 1


def test_digest_scanner_exception_is_exact_and_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = ARTIFACT_PATH.read_bytes()
    lines = data.decode().splitlines()
    indices = [
        i + 1
        for i, line in enumerate(lines)
        if '"benchmark_definition_sha256":' in line or '"registry_sha256":' in line
    ]
    assert len(indices) == 5
    finding = {"type": "Hex High Entropy String", "line_number": indices[0]}
    assert all(
        verified_registry_digest(str(ARTIFACT_PATH), {**finding, "line_number": i}) for i in indices
    )
    assert not verified_registry_digest("another.json", finding)
    assert not verified_registry_digest(str(ARTIFACT_PATH), {**finding, "type": "Secret Keyword"})
    assert not verified_registry_digest(str(ARTIFACT_PATH), {**finding, "line_number": 1})
    monkeypatch.chdir(tmp_path)
    ARTIFACT_PATH.parent.mkdir()
    ARTIFACT_PATH.write_bytes(data + b" ")
    assert not verified_registry_digest(str(ARTIFACT_PATH), finding)


def test_tsmom_deferred_and_primitive_still_available() -> None:
    from trading_ecosystem.research.indicators import trailing_return

    assert callable(trailing_return) and len(BenchmarkId) == 4
    assert "DEFERRED_NOT_REGISTERED" in Path("docs/PHASE3_2_BENCHMARK_REGISTRY.md").read_text(
        encoding="utf-8"
    )
