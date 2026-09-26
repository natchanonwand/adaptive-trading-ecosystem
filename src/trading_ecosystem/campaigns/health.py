"""Fresh read-only start/continuity checks, limited to loopback services and frozen SDK reads."""

import ast
import json
from datetime import datetime
from http.client import HTTPConnection
from pathlib import Path

from sqlalchemy import Engine, text

from trading_ecosystem.campaigns.contracts import RealEaQualificationCampaign
from trading_ecosystem.domain.primitives import utc_timestamp
from trading_ecosystem.monitoring.queries import read_view
from trading_ecosystem.mt5.calibration import require_demo
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.mt5.normalization import account_identity
from trading_ecosystem.observer.runtime import ObserverClient


def audit_read_only() -> bool:
    roots = [
        Path(__file__).parent,
        Path(__file__).parents[1] / "observer",
        Path(__file__).parents[1] / "mt5",
    ]
    forbidden = {"order" + "_send", "order" + "_check"}
    for root in roots:
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Attribute) and node.attr in forbidden:
                    return False
                if isinstance(node, ast.Name) and node.id in forbidden:
                    return False
    return True


def local_get(port: int, path: str) -> tuple[int, bytes]:
    conn = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError("HEALTH_RESPONSE_TOO_LARGE")
        return response.status, body
    finally:
        conn.close()


def account_guard(spec: RealEaQualificationCampaign, client: ObserverClient) -> Record:
    account, terminal = client.account_info(), client.terminal_info()
    if type(account.get("trade_mode")) is not int or account["trade_mode"] != 0:
        raise ValueError("INVALIDATED_ACCOUNT_NOT_DEMO")
    if (
        account_identity(account) != spec.account_scope
        or account.get("server") != spec.server
        or account.get("company") != spec.broker
    ):
        raise ValueError("INVALIDATED_ACCOUNT_SWITCH")
    if terminal.get("build") != spec.terminal_build:
        raise ValueError("INVALIDATED_TERMINAL_BUILD_CHANGE")
    require_demo(account, terminal)
    if terminal.get("trade_allowed") is not True:
        raise ValueError("EA_ALGO_PERMISSION_NOT_ENABLED_BY_USER")
    return dict(connected=True, account_scope=str(spec.account_scope), environment="DEMO")


def inspect_health(
    spec: RealEaQualificationCampaign, client: ObserverClient, engine: Engine, now: datetime
) -> Record:
    checks: Record = dict(
        candidate=spec.metadata.ready(),
        read_only=audit_read_only(),
        mt5=False,
        postgresql=False,
        bridge=False,
        observer=False,
        dashboard=False,
        window=spec.window_start <= now < spec.window_end,
    )
    reasons = []
    try:
        account_guard(spec, client)
        checks["mt5"] = True
    except Exception as exc:
        reasons.append(str(exc) if isinstance(exc, ValueError) else "MT5_READ_FAILED")
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            checks["postgresql"] = conn.execute(text("SELECT 1")).scalar_one() == 1
            view = read_view(conn, "system", spec.bridge_stream_id)
        scope = view["scope"] or {}
        broker_rows = [r for r in view["items"] if r["values"].get("component") == "broker"]
        latest = max(broker_rows, key=lambda r: r["sequence"]) if broker_rows else None
        checks["bridge"] = bool(
            scope.get("environment") == "DEMO"
            and scope.get("account_id") == str(spec.account_scope)
            and latest
            and latest["values"].get("state") == "HEALTHY"
            and 0 <= (now - utc_timestamp(latest["occurred_at"])).total_seconds() <= 10
        )
    except Exception:
        reasons.append("POSTGRESQL_OR_BRIDGE_EVIDENCE_UNAVAILABLE")
    try:
        health_status, health_body = local_get(spec.api_port, "/health")
        api_health = json.loads(health_body)
        status, body = local_get(spec.api_port, "/api/v1/observer")
        payload = json.loads(body)
        checks["observer"] = (
            status == 200
            and health_status == 200
            and api_health.get("read_only") is True
            and api_health.get("status") == "HEALTHY"
            and api_health.get("database") == "HEALTHY"
            and isinstance(payload.get("sessions"), list)
        )
    except Exception:
        reasons.append("OBSERVER_API_UNAVAILABLE")
    try:
        status, body = local_get(spec.dashboard_port, "/")
        checks["dashboard"] = status == 200 and b'id="root"' in body
    except Exception:
        reasons.append("DASHBOARD_UNAVAILABLE")
    return dict(
        observed_at=now.isoformat(), checks=checks, passed=all(checks.values()), reasons=reasons
    )
