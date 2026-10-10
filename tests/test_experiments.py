"""Synthetic pre-registration tests; no real search or candidate execution."""

from datetime import date
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from trading_ecosystem.experiments.contracts import (
    ExperimentCampaign,
    ExperimentDefinition,
    Parameter,
)
from trading_ecosystem.experiments.governance import (
    candidate_at,
    evaluate_constraints,
    feature_cutoff,
)


def definition_data() -> dict[str, Any]:
    return dict(
        project_id=str(UUID(int=1)),
        candidate_id=str(UUID(int=2)),
        baseline_configuration_id=str(UUID(int=3)),
        baseline_identity="a" * 64,
        hypothesis="Synthetic fixture: pre-registered sensitivity hypothesis",
        parameter_space={
            "parameters": [
                dict(
                    parameter_name="Period",
                    native_key="Period",
                    kind="INTEGER",
                    baseline="2",
                    minimum="1",
                    maximum="3",
                    step="1",
                    reason="Synthetic sensitivity",
                    provenance="USER_DECLARATION",
                    source_reference="Hand-authored test fixture",
                    categorical=False,
                    ordered=True,
                )
            ]
        },
        budget=dict(
            maximum_configurations=3,
            maximum_native_executions=3,
            method="RANDOM_SEEDED",
            random_seed=42,
            maximum_wall_seconds=60,
        ),
        split_plan={
            "splits": [
                dict(start="2020-01-01", end="2020-02-01", purpose="DEVELOPMENT"),
                dict(start="2020-02-01", end="2020-03-01", purpose="VALIDATION"),
                dict(start="2020-03-01", end="2020-04-01", purpose="LOCKED_OOS"),
            ]
        },
        objectives=[
            dict(
                metric="RETURN_R",
                direction="MAXIMIZE",
                definition="Return divided by declared risk",
            )
        ],
        evaluation_method="PARETO_REVIEW",
        constraints=[
            dict(
                metric="TRADE_COUNT",
                comparator="AT_LEAST",
                threshold="1",
                rationale="Minimum activity",
            )
        ],
        cost_assumptions="Synthetic fees; no production qualification",
        broker="Synthetic demo",
        symbol="XAUUSDm",
        timeframe="H1",
        data_identity="b" * 64,
        evidence_classification="EXPLORATORY_COST_MODELED",
    )


def definition() -> ExperimentDefinition:
    return ExperimentDefinition.model_validate(definition_data())


def test_deep_immutability_and_identity() -> None:
    d = definition()
    assert ExperimentDefinition.model_validate_json(d.model_dump_json()) == d
    assert definition().identity == d.identity
    with pytest.raises(ValidationError):
        d.hypothesis = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        d.parameter_space.parameters[0].baseline = "3"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        d.budget.maximum_configurations = 4  # type: ignore[misc]
    value = definition_data()
    value["hypothesis"] = "A different registered question"
    changed = ExperimentDefinition.model_validate(value)
    assert changed.identity != d.identity
    assert (
        ExperimentCampaign(definition_identity=changed.identity).identity
        != ExperimentCampaign(definition_identity=d.identity).identity
    )


@pytest.mark.parametrize(
    "change",
    [
        {"baseline": "4"},
        {"minimum": "4"},
        {"step": "0"},
        {"baseline": "1.5"},
        {"step": "nan"},
        {"choices": ["1", "1"]},
        {"provenance": "BINARY_REVERSE_ENGINEERING"},
        {"source_reference": "UNKNOWN"},
        {"native_key": ""},
        {"maximum": "1e100000"},
        {"kind": "FLOAT"},
        {"ordered": False},
        {"conditional": {"native_key": "Unknown", "equals": "1"}},
    ],
)
def test_parameter_rejections(change: dict[str, Any]) -> None:
    value = definition_data()
    value["parameter_space"]["parameters"][0].update(change)
    with pytest.raises((ValidationError, ValueError)):
        ExperimentDefinition.model_validate(value)


def test_discrete_and_conditional() -> None:
    value = definition_data()
    p = value["parameter_space"]["parameters"][0]
    p.update(choices=["1", "2", "3"], minimum=None, maximum=None, step=None)
    value["parameter_space"]["parameters"].append(
        {
            **p,
            "native_key": "Child",
            "parameter_name": "Child",
            "conditional": {"native_key": "Period", "equals": "2"},
        }
    )
    d = ExperimentDefinition.model_validate(value)
    assert d.parameter_space.parameters[1].conditional is not None
    assert d.parameter_space.parameters[0].domain() == ("1", "2", "3")
    assert Parameter.model_validate(
        {
            **p,
            "kind": "BOOLEAN",
            "baseline": "false",
            "choices": ["false", "true"],
            "categorical": True,
            "ordered": False,
        }
    ).domain() == ("false", "true")


@pytest.mark.parametrize(
    "purpose,index", [("LOCKED_OOS", 0), ("DEVELOPMENT", 1), ("VALIDATION", 2)]
)
def test_split_order(purpose: str, index: int) -> None:
    value = definition_data()
    value["split_plan"]["splits"][index]["purpose"] = purpose
    with pytest.raises(ValidationError):
        ExperimentDefinition.model_validate(value)


@pytest.mark.parametrize(
    "change", [{"start": "2020-01-15"}, {"end": "2020-02-01"}, {"locked": False}]
)
def test_overlap_empty_or_unlock(change: dict[str, Any]) -> None:
    value = definition_data()
    value["split_plan"]["splits"][1].update(change)
    with pytest.raises(ValidationError):
        ExperimentDefinition.model_validate(value)


def test_seeded_grid_and_budget_contract() -> None:
    d = definition()
    assert [candidate_at(d, i) for i in range(3)] == [
        candidate_at(definition(), i) for i in range(3)
    ]
    assert all(
        candidate_at(d, i).split_identity == d.split_plan.splits[0].identity for i in range(3)
    )
    with pytest.raises(ValueError, match="BUDGET"):
        candidate_at(d, 3)
    value = definition_data()
    value["budget"].update(method="GRID", random_seed=None)
    grid = ExperimentDefinition.model_validate(value)
    assert [candidate_at(grid, i).parameter_values for i in range(3)] == [
        (("Period", "1"),),
        (("Period", "2"),),
        (("Period", "3"),),
    ]
    with pytest.raises(TypeError):
        candidate_at(d, 0, validation_metrics={})  # type: ignore[call-arg]
    assert not ExperimentCampaign(definition_identity=d.identity).execution_enabled


@pytest.mark.parametrize(
    "change",
    [
        {"random_seed": None},
        {"method": "ADAPTIVE"},
        {"maximum_configurations": 0},
        {"maximum_native_executions": 2},
        {"maximum_wall_seconds": 0},
        {"maximum_workers": 2},
    ],
)
def test_budget_rejections(change: dict[str, Any]) -> None:
    value = definition_data()
    value["budget"].update(change)
    with pytest.raises(ValidationError):
        ExperimentDefinition.model_validate(value)


@pytest.mark.parametrize("observed", ["2020-02-01", "2020-03-01", "2019-12-31"])
def test_no_future_validation_oos(observed: str) -> None:
    with pytest.raises(ValueError, match="FORBIDDEN"):
        feature_cutoff(definition(), date.fromisoformat(observed))


def test_zero_trade_valid_but_ineligible() -> None:
    assert evaluate_constraints(definition(), (("TRADE_COUNT", "0"),)) == (
        "REJECTED",
        ("TRADE_COUNT",),
    )
    assert (
        evaluate_constraints(definition(), (("TRADE_COUNT", None),))[0] == "INSUFFICIENT_EVIDENCE"
    )
    assert evaluate_constraints(definition(), (("TRADE_COUNT", "1"),)) == ("ELIGIBLE", ())


@pytest.mark.parametrize("metric", ["NET_PROFIT", "UNREGISTERED_METRIC"])
def test_objective_validation(metric: str) -> None:
    value = definition_data()
    value["objectives"][0]["metric"] = metric
    with pytest.raises(ValidationError):
        ExperimentDefinition.model_validate(value)
