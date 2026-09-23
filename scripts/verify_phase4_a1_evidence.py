"""Verify preserved DEMO answers, domain replay and the read-only retained sample."""

import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine

from trading_ecosystem.monitoring.contracts import Scope
from trading_ecosystem.mt5.calibration import retained_observations
from trading_ecosystem.mt5.calibration_verify import public_report, verify_report
from trading_ecosystem.mt5.cost_profile import profile_deals, profile_spreads


def main() -> None:
    source = Path(".local/phase4_a1/calibration-20260922-complete.json")
    hashes = json.loads(Path(".local/phase4_a1/accepted-hashes.json").read_text())
    for name, expected in hashes.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError("CALIBRATION_ARTIFACT_HASH_MISMATCH")
    report = json.loads(source.read_text())
    verify_report(report)
    presentation = json.loads(Path("reports/mt5_broker_economics_calibration.json").read_text())
    if presentation != public_report(report):
        raise ValueError("PUBLIC_CALIBRATION_REPORT_MISMATCH")
    prior = json.loads(Path(".local/phase4_a/demo-smoke-accepted.json").read_text())
    engine = create_engine(os.environ["TE_DATABASE_URL"])
    try:
        retained, identity = retained_observations(engine, Scope.model_validate(prior["scope"]))
    finally:
        engine.dispose()
    if identity != report["source_evidence"]:
        raise ValueError("RETAINED_EVIDENCE_CHANGED")
    costs = profile_deals([r["body"] for r in retained if r["kind"] == "DEAL"])
    spreads = profile_spreads(
        [(r["external_id"], r["body"]) for r in retained if r["kind"] == "QUOTE"]
    )
    if costs != report["historical_costs"] or spreads != report["spreads"]:
        raise ValueError("RETAINED_PROFILE_REPLAY_MISMATCH")
    print("PASS: calibration hashes; 144 profit rows; 24 margin rows; 144 risk scenarios replayed")
    print(
        f"PASS: {costs['deal_count']} unique deals; retained sample hashes and profiles unchanged"
    )


if __name__ == "__main__":
    main()
