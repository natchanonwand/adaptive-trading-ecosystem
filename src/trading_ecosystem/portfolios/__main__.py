"""Explicit aggregation and verification of frozen episode artifacts only."""

import argparse
from pathlib import Path

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.portfolios.evidence import (
    build,
    load_inputs,
    verify_outputs,
    write_exclusive,
)
from trading_ecosystem.portfolios.report import report
from trading_ecosystem.simulation.hashing import digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["generate", "verify"])
    args = parser.parse_args()
    inputs, interval = load_inputs()
    outputs = build(inputs, interval)
    run_id = "phase3_3c-" + digest([item["result_sha256"] for item in outputs])[:24]
    root = Path("data/research/phase3_3c") / run_id
    if args.mode == "generate":
        root.mkdir(parents=True, exist_ok=True)
        for result in outputs:
            write_exclusive(
                root / (result["portfolio_id"] + "--" + result["layer"] + ".json"), result
            )
    outputs = verify_outputs(root, outputs)
    with arithmetic_context():
        text = report(run_id, outputs)
    path = Path("PHASE3_3C_REPORT.md")
    if args.mode == "generate":
        if path.exists() and path.read_text(encoding="utf-8") != text:
            raise ValueError("EXISTING_REPORT_CONFLICT")
        path.write_text(text, encoding="utf-8", newline="\n")
    elif path.read_text(encoding="utf-8") != text:
        raise ValueError("PORTFOLIO_REPORT_EVIDENCE_MISMATCH")
    print(
        "PASS " + run_id + ": four R-space and four synthetic results; replay and report verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
