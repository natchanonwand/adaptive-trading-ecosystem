from copy import deepcopy
from typing import Any

import pytest

from trading_ecosystem.tester.workspace_attestation import assess_workspace


def payload() -> dict[str, Any]:
    return {
        "schema": "RUNTIME_WORKSPACE_V1",
        "valid": True,
        "charts": [
            {
                "symbol": "EURUSD",
                "period": p,
                "expert_name": "",
                "script_name": "ResearchWorkspaceAttestor" if i == 0 else "",
                "host": i == 0,
            }
            for i, p in enumerate([16408, 16385, 16388, 30])
        ],
    }


def test_clean_unique_and_volatile_fields_excluded() -> None:
    value = payload()
    profiles = {"Euro": ["EURUSD"] * 4, "Default": ["XAUUSDm"] * 13}
    before = assess_workspace(value, profiles)
    value["ProfileLast"] = "Default"
    for i, row in enumerate(value["charts"]):
        row.update(chart_id=i + 100, timestamp="ignored", ordinal=i)
    value["charts"].reverse()
    assert assess_workspace(value, profiles) == before
    assert before["state"] == "VERIFIED_EURO_WORKSPACE"


@pytest.mark.parametrize(
    "field,value,index",
    [
        ("expert_name", "Smart Hedge Pro", 0),
        ("expert_name", "Other", 1),
        ("script_name", "Other", 0),
        ("script_name", "ResearchWorkspaceAttestor", 1),
    ],
)
def test_contamination(field: str, value: str, index: int) -> None:
    body = payload()
    body["charts"][index][field] = value
    with pytest.raises(ValueError, match="CONTAMINATED"):
        assess_workspace(body, {"Euro": ["EURUSD"] * 4})


def test_ambiguous_not_ready() -> None:
    assert (
        assess_workspace(payload(), {"Euro": ["EURUSD"] * 4, "Other": ["EURUSD"] * 4})["state"]
        == "CLEAN_WORKSPACE_PROFILE_AMBIGUOUS"
    )


def test_mismatch_and_changed_inventory() -> None:
    body = payload()
    before = assess_workspace(body, {"Euro": ["EURUSD"] * 4})
    body["charts"][1]["symbol"] = "GBPUSD"
    after = assess_workspace(body, {"Euro": ["EURUSD"] * 4})
    assert after["state"] == "CONTAMINATED_OR_MISMATCHED"
    assert after["fingerprint"] != before["fingerprint"]


@pytest.mark.parametrize(
    "body",
    [
        {"ProfileLast": "Euro"},
        {"arguments": ["/profile:Euro"]},
        {"config": "[Charts]\nProfileLast=Euro"},
    ],
)
def test_requested_or_persisted_profile_not_runtime_evidence(body: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        assess_workspace(body, {"Euro": ["EURUSD"] * 4})


def test_missing_self_rejected() -> None:
    body = deepcopy(payload())
    body["charts"][0]["script_name"] = ""
    with pytest.raises(ValueError):
        assess_workspace(body, {"Euro": ["EURUSD"] * 4})
