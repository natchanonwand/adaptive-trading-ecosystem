"""Fail-closed interpretation of read-only native workspace inventories."""

from typing import Any

from trading_ecosystem.tester.qualification import digest

ATTESTOR = "ResearchWorkspaceAttestor"


def assess_workspace(payload: dict[str, Any], profiles: dict[str, list[str]]) -> dict[str, Any]:
    if payload.get("schema") != "RUNTIME_WORKSPACE_V1" or payload.get("valid") is not True:
        raise ValueError("BLOCKED_WORKSPACE_EVIDENCE_INVALID")
    rows = payload.get("charts")
    if not isinstance(rows, list) or not rows or len(rows) > 100:
        raise ValueError("BLOCKED_WORKSPACE_EVIDENCE_INVALID")
    normalized: list[dict[str, Any]] = []
    hosts = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("BLOCKED_WORKSPACE_EVIDENCE_INVALID")
        symbol, period = row.get("symbol"), row.get("period")
        expert, script, host = row.get("expert_name"), row.get("script_name"), row.get("host")
        if (
            not isinstance(symbol, str)
            or not symbol
            or type(period) is not int
            or period <= 0
            or not isinstance(expert, str)
            or not isinstance(script, str)
            or type(host) is not bool
        ):
            raise ValueError("BLOCKED_WORKSPACE_EVIDENCE_INVALID")
        if expert or (script and (script != ATTESTOR or not host)):
            raise ValueError("BLOCKED_PROFILE_CONTAMINATED")
        if host:
            hosts += 1
            if script != ATTESTOR:
                raise ValueError("BLOCKED_ATTESTOR_SELF_IDENTITY")
        normalized.append(
            {"symbol": symbol, "period": period, "expert_name": "", "script_name": ""}
        )
    if hosts != 1:
        raise ValueError("BLOCKED_ATTESTOR_SELF_IDENTITY")
    normalized.sort(key=lambda row: (str(row["symbol"]), int(row["period"])))
    symbols = sorted(str(row["symbol"]) for row in normalized)
    matches = sorted(name for name, expected in profiles.items() if sorted(expected) == symbols)
    state = (
        "VERIFIED_EURO_WORKSPACE"
        if matches == ["Euro"]
        else "CLEAN_WORKSPACE_PROFILE_AMBIGUOUS"
        if "Euro" in matches
        else "CONTAMINATED_OR_MISMATCHED"
    )
    return {
        "state": state,
        "charts": normalized,
        "fingerprint": digest(normalized),
        "matches": matches,
    }
