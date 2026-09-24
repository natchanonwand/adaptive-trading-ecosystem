"""Build, export, validate and summarize immutable observations entirely offline."""

import argparse
import json
from pathlib import Path

from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.features.dataset import export, validate
from trading_ecosystem.features.registry import CATALOG


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "export"):
        builder = sub.add_parser(command)
        builder.add_argument("--source", action="append", required=True, type=Path)
        builder.add_argument("--output", required=True, type=Path)
        builder.add_argument("--config", type=Path)
    for command in ("validate", "summarize", "serve"):
        reader = sub.add_parser(command)
        reader.add_argument("dataset", type=Path)
        if command == "serve":
            reader.add_argument("--port", type=int, default=8765)
    registry = sub.add_parser("registry")
    registry.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command in ("build", "export"):
        config = (
            BuildConfig.model_validate_json(args.config.read_text())
            if args.config
            else BuildConfig()
        )
        manifest = export(args.source, args.output, config)
        print(
            json.dumps(
                dict(feature_set_id=manifest["feature_set_id"], datasets=manifest["datasets"]),
                indent=2,
            )
        )
    elif args.command == "registry":
        args.output.write_text(
            json.dumps([d.model_dump(mode="json") for d in CATALOG], indent=2) + "\n",
            encoding="utf-8",
        )
    elif args.command == "serve":
        from trading_ecosystem.features.api import FeatureServer

        with FeatureServer(args.dataset, args.port) as server:
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    else:
        manifest = validate(args.dataset)
        print(
            json.dumps(
                manifest["summary"]
                if args.command == "summarize"
                else {"status": "PASS", "feature_set_id": manifest["feature_set_id"]},
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
