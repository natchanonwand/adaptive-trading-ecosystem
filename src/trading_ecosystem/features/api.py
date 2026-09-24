"""Offline loopback-only feature quality endpoint, with no broker or database attachment."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from trading_ecosystem.features.dataset import validate


class FeatureServer(ThreadingHTTPServer):
    def __init__(self, dataset: Path, port: int = 8765) -> None:
        manifest = validate(dataset)
        self.feature_status = dict(
            status="VERIFIED_OFFLINE",
            read_only=True,
            feature_set_id=manifest["feature_set_id"],
            dataset_type=manifest["dataset_type"],
            sessions=len(manifest["session_ids"]),
            datasets={
                k: {"rows": v["rows"], "columns": v["columns"]}
                for k, v in manifest["datasets"].items()
            },
            causal_feature_count=manifest["causal_feature_count"],
            outcome_field_count=manifest["outcome_field_count"],
            missingness={
                k: v["missing_count"] for k, v in manifest["summary"]["episode_features"].items()
            },
            source_confidence=manifest["summary"]["episode_features"]["source_confidence"],
            real_ea_qualification="NOT_PROVIDED"
            if manifest["dataset_type"] == "SYNTHETIC_QUALIFICATION"
            else "UNASSESSED",
        )
        super().__init__(("127.0.0.1", port), FeatureHandler)


class FeatureHandler(BaseHTTPRequestHandler):
    server: FeatureServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def respond(self, status: int, body: object) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.headers.get("Origin") is not None or self.headers.get("Host") not in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }:
            self.respond(403, {"error": "LOCAL_CLIENT_REQUIRED"})
        elif self.path != "/api/v1/features":
            self.respond(404, {"error": "OFFLINE_FEATURE_ENDPOINT_ONLY"})
        else:
            self.respond(200, self.server.feature_status)

    def do_POST(self) -> None:
        self.respond(405, {"error": "READ_ONLY"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST
