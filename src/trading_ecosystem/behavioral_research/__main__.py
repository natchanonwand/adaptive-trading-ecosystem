"""Offline Phase 4D CLI; inputs must be verified Phase 4C datasets."""

import argparse
from pathlib import Path

from trading_ecosystem.behavioral_research.contracts import ResearchConfig, canonical
from trading_ecosystem.behavioral_research.engine import compare, research
from trading_ecosystem.behavioral_research.loader import load
from trading_ecosystem.behavioral_research.reports import export, markdown, validate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("validate", "fingerprint", "analyze", "compare", "report", "serve")
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--right", type=Path)
    parser.add_argument("--right-config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--research-export", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    config = (
        ResearchConfig.model_validate_json(args.config.read_bytes())
        if args.config
        else ResearchConfig()
    )
    if args.command == "serve":
        from trading_ecosystem.behavioral_research.api import ResearchServer

        with ResearchServer(args.dataset, args.port) as server:
            server.serve_forever()
    elif args.command == "validate":
        result = (
            validate(args.dataset) if args.research_export else load(args.dataset, config).manifest
        )
        print(canonical(result))
    elif args.command == "compare":
        if args.right is None:
            parser.error("compare requires --right Phase 4C dataset")
        right_config = (
            ResearchConfig.model_validate_json(args.right_config.read_bytes())
            if args.right_config
            else config
        )
        print(
            canonical(compare(research(args.dataset, config), research(args.right, right_config)))
        )
    elif args.output is not None:
        if args.command != "analyze":
            parser.error("--output is supported by analyze; it writes all research artifacts")
        print(canonical(export(args.dataset, args.output, config)))
    else:
        result = research(args.dataset, config)
        print(
            markdown(result)
            if args.command == "report"
            else canonical(result["fingerprint"] if args.command == "fingerprint" else result)
        )


if __name__ == "__main__":
    main()
