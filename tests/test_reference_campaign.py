"""Reference protocol and authorization are pure; never execute native code."""

from copy import deepcopy
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_ecosystem.experiments.authorization import capability, verify_capability
from trading_ecosystem.experiments.campaigns import bindings, generate, select_development
from trading_ecosystem.experiments.contracts import ExperimentDefinition, digest
from trading_ecosystem.experiments.reference_contract import ReferenceDefinition, parse_definition
from trading_ecosystem.experiments.reference_preparation import definition


def fixture() -> ReferenceDefinition:
    build = {
        "content": {"source_sha256": "a" * 64, "canonical_ex5_sha256": "b" * 64},
        "identity": "c" * 64,
    }
    return definition(
        str(uuid5(NAMESPACE_URL, "project")),
        str(uuid5(NAMESPACE_URL, "candidate")),
        str(uuid5(NAMESPACE_URL, "baseline")),
        "d" * 64,
        build,
        "e" * 64,
    )


def body() -> dict[str, Any]:
    d = fixture()
    plan = {"candidates": generate(d), "bindings": bindings(d)}
    return {
        "id": str(uuid5(NAMESPACE_URL, digest(plan))),
        "plan": plan,
        "plan_identity": digest(plan),
        "definition": d.model_dump(mode="json"),
    }


def test_exact_grid_identity_defaults_and_reparse() -> None:
    d = fixture()
    assert parse_definition(d.model_dump(mode="json")) == d
    candidates = generate(d)
    assert candidates == generate(d) and len({c["identity"] for c in candidates}) == 9
    assert [c["assignments"] for c in candidates] == [
        {"InpFastEmaPeriod": str(f), "InpSlowEmaPeriod": str(s)}
        for s in (60, 100, 140)
        for f in (10, 20, 30)
    ]
    assert all(
        int(c["assignments"]["InpFastEmaPeriod"]) < int(c["assignments"]["InpSlowEmaPeriod"])
        for c in candidates
    )
    assert [p.baseline for p in d.parameter_space.parameters] == ["20", "100"]
    assert d.budget.maximum_native_executions == 11
    assert (d.development_limit, d.validation_limit) == (9, 2)


@pytest.mark.parametrize(
    "field,value",
    [
        ("canonical_ex5_sha256", "f" * 64),
        ("source_sha256", "f" * 64),
        ("build_identity", "f" * 64),
        ("candidate_id", str(uuid5(NAMESPACE_URL, "other"))),
        ("baseline_identity", "f" * 64),
    ],
)
def test_changed_binding_invalidates_grant(field: str, value: str) -> None:
    b = body()
    content = capability(b, {"DEMO": True})
    b["execution_authorization"] = {
        "state": "AUTHORIZED",
        "content": content,
        "identity": digest(content),
    }
    b["definition"][field] = value
    with pytest.raises(ValueError):
        verify_capability(b, {"DEMO": True}, "DEVELOPMENT")


@pytest.mark.parametrize(
    "mutation", ["parameter", "budget", "split", "metric", "provenance", "unbounded"]
)
def test_invalid_reference_contract_fails_closed(mutation: str) -> None:
    data = fixture().model_dump(mode="json")
    if mutation == "parameter":
        data["parameter_space"]["parameters"][0]["native_key"] = "Guess"
    if mutation == "budget":
        data["budget"]["maximum_native_executions"] = 12
    if mutation == "split":
        data["split_plan"]["splits"][1]["start"] = "2026-03-31"
    if mutation == "metric":
        data["objectives"][0]["metric"] = "RETURN_R"
    if mutation == "provenance":
        data["parameter_space"]["parameters"][0]["source_reference"] = "UNKNOWN"
    if mutation == "unbounded":
        data["parameter_space"]["parameters"][0]["choices"] = []
    with pytest.raises(ValueError):
        parse_definition(data)


def test_authorization_exact_review_no_mutation_oos_denied() -> None:
    b = body()
    before = deepcopy(b)
    content = capability(b, {"DEMO": True})
    assert content == capability(b, {"DEMO": True}) and b == before
    with pytest.raises(ValueError):
        verify_capability(b, {"DEMO": True}, "DEVELOPMENT")
    b["execution_authorization"] = {
        "state": "AUTHORIZED",
        "content": content,
        "identity": digest(content),
    }
    for stage in ("DEVELOPMENT", "VALIDATION"):
        verify_capability(b, {"DEMO": True}, stage)
    with pytest.raises(ValueError):
        verify_capability(b, {"DEMO": True}, "LOCKED_OOS")
    with pytest.raises(ValueError):
        verify_capability(b, {"DEMO": False}, "DEVELOPMENT")
    b["id"] = str(uuid5(NAMESPACE_URL, "other"))
    with pytest.raises(ValueError):
        verify_capability(b, {"DEMO": True}, "DEVELOPMENT")


def test_top_two_activity_and_identity_tiebreak() -> None:
    runs = [
        dict(
            purpose="DEVELOPMENT",
            configuration_identity=key,
            status="COMPLETE",
            observation={"metrics": {"NET_PROFIT": profit, "TRADE_COUNT": count}},
        )
        for key, profit, count in [
            ("c", "10", "10"),
            ("b", "10", "10"),
            ("a", "20", "10"),
            ("z", "99", "0"),
        ]
    ]
    selected, decisions = select_development(fixture(), runs)
    assert selected == ["a", "b"] and decisions["z"] == "CONSTRAINT_REJECTED"


def test_old_profit_only_contract_remains_rejected() -> None:
    data = fixture().model_dump(mode="json")
    with pytest.raises(ValueError):
        ExperimentDefinition.model_validate(data)


def test_half_open_splits_remain_sealed() -> None:
    splits = fixture().split_plan.splits
    assert all(s.locked for s in splits)
    assert splits[0].end == splits[1].start and splits[1].end == splits[2].start
    assert str(splits[2].end) == "2026-07-01"
