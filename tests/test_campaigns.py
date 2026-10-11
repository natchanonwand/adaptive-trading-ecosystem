"""Pure synthetic campaign generation, eligibility and offline observation tests."""

from copy import deepcopy
from typing import Any
from uuid import UUID

import pytest

from tests.test_experiments import definition_data
from trading_ecosystem.experiments.baseline_boundary import inputs
from trading_ecosystem.experiments.campaigns import generate, observation, select_development
from trading_ecosystem.experiments.contracts import ExperimentDefinition


def definition(**changes: Any) -> ExperimentDefinition:
    data = definition_data()
    data["budget"].update(method="GRID", random_seed=None, maximum_native_executions=6)
    data["objectives"] = [
        {"metric": "TRADE_COUNT", "direction": "MAXIMIZE", "definition": "Declared count"}
    ]
    data["constraints"][0]["threshold"] = "0"
    data["evidence_classification"] = "EXPLORATORY_GROSS"
    data.update(changes)
    return ExperimentDefinition.model_validate(data)


def observed(key: str, count: str | None = "1", status: str = "COMPLETE") -> dict[str, Any]:
    return {
        "configuration_identity": key,
        "purpose": "DEVELOPMENT",
        "status": status,
        "observation": {"metrics": {"TRADE_COUNT": count}},
    }


def test_grid_order_bounds_and_identity() -> None:
    d = definition()
    values = generate(d)
    assert [c["assignments"] for c in values] == [{"Period": str(i)} for i in (1, 2, 3)]
    assert values == generate(d)
    assert len({c["identity"] for c in values}) == 3
    assert generate(definition(hypothesis="new hypothesis"))[0]["identity"] != values[0]["identity"]


def test_seeded_duplicates_collapse_without_replenishment() -> None:
    data = definition().model_dump(mode="json")
    data["budget"].update(
        method="RANDOM_SEEDED",
        random_seed=2,
        maximum_configurations=10,
        maximum_native_executions=10,
    )
    d = ExperimentDefinition.model_validate(data)
    result = generate(d)
    assert result == generate(d) and len(result) <= 3
    assert len({tuple(c["assignments"].items()) for c in result}) == len(result)
    assert all(c["ordinal"] < 10 for c in result)


def test_grid_exhaustion_and_semantic_numeric_duplicates() -> None:
    data = definition().model_dump(mode="json")
    p = data["parameter_space"]["parameters"][0]
    p.update(
        kind="DECIMAL",
        minimum=None,
        maximum=None,
        step=None,
        choices=["1", "1.0", "2"],
        baseline="1",
    )
    data["budget"].update(maximum_configurations=8, maximum_native_executions=8)
    result = generate(ExperimentDefinition.model_validate(data))
    assert [c["assignments"]["Period"] for c in result] == ["1", "2"]


@pytest.mark.parametrize("mode", ["GRID", "RANDOM_SEEDED"])
def test_conditional_inactive_inputs_keep_baseline(mode: str) -> None:
    data = definition().model_dump(mode="json")
    p = deepcopy(data["parameter_space"]["parameters"][0])
    p.update(
        native_key="Other",
        parameter_name="Other",
        conditional={"native_key": "Period", "equals": "3"},
    )
    data["parameter_space"]["parameters"].append(p)
    data["budget"].update(method=mode, random_seed=3 if mode == "RANDOM_SEEDED" else None)
    for c in generate(ExperimentDefinition.model_validate(data)):
        if c["assignments"]["Period"] != "3":
            assert c["assignments"]["Other"] == "2"


def test_constraints_precede_objectives_and_ties_stay_ordered() -> None:
    selected, states = select_development(
        definition(),
        [
            observed("a", "2"),
            observed("b", "-1"),
            observed("c", "2"),
            observed("d", None),
            observed("e", "9", "TIMEOUT"),
        ],
    )
    assert selected == ["a", "c"]
    assert states["b"] == "CONSTRAINT_REJECTED"
    assert states["d"] == "CONSTRAINT_INSUFFICIENT_EVIDENCE"
    assert states["e"] == "EXECUTION_FAILURE"


def test_pareto_and_lexicographic_are_distinct_declared_rules() -> None:
    objectives = [
        {"metric": "TRADE_COUNT", "direction": "MAXIMIZE", "definition": "count"},
        {"metric": "NET_PROFIT", "direction": "MINIMIZE", "definition": "synthetic ordering"},
    ]
    runs = [observed("a", "2"), observed("b", "1"), observed("c", "1")]
    for r, value in zip(runs, ["9", "1", "2"], strict=True):
        r["observation"]["metrics"]["NET_PROFIT"] = value
    assert select_development(definition(objectives=objectives), runs)[0] == ["a", "b"]
    assert select_development(
        definition(objectives=objectives, evaluation_method="DECLARED_LEXICOGRAPHIC"), runs
    )[0] == ["a"]


@pytest.mark.parametrize("purpose", ["VALIDATION", "LOCKED_OOS"])
def test_non_development_metrics_rejected(purpose: str) -> None:
    run = observed("a")
    run["purpose"] = purpose
    with pytest.raises(ValueError, match="NON_DEVELOPMENT"):
        select_development(definition(), [run])


@pytest.mark.parametrize("count", ["0", "1", "100"])
def test_linked_observation_and_zero_trade_semantics(count: str) -> None:
    value = {
        "metrics": {"TRADE_COUNT": count, "PROFIT_FACTOR": None},
        "baseline_run_id": str(UUID(int=8)),
        "evidence_identity": "a" * 64,
        "result_identity": "b" * 64,
    }
    assert observation(value) == value


@pytest.mark.parametrize("count", [None, "-1", "1.5", "NaN", "Infinity", 4])
def test_invalid_observations_rejected(count: Any) -> None:
    with pytest.raises((ValueError, ArithmeticError)):
        observation(
            {
                "metrics": {"TRADE_COUNT": count},
                "baseline_run_id": str(UUID(int=8)),
                "evidence_identity": "a" * 64,
                "result_identity": "b" * 64,
            }
        )


def test_zero_denominator_not_synthesized() -> None:
    with pytest.raises(ValueError, match="ZERO_TRADE"):
        observation(
            {
                "metrics": {"TRADE_COUNT": "0", "PROFIT_FACTOR": "0"},
                "baseline_run_id": str(UUID(int=8)),
                "evidence_identity": "a" * 64,
                "result_identity": "b" * 64,
            }
        )


def test_merge_inputs_preserves_other_defaults_and_never_enables_optimization() -> None:
    assert inputs("Other=5\nPeriod=2", {"Period": "3"}) == "Other=5\nPeriod=3"


@pytest.mark.parametrize("value", ["a\nb=2", "1||0||1||4||Y", "\x00"])
def test_input_injection_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        inputs(None, {"Period": value})
