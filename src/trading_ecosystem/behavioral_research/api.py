"""A validated, immutable research summary on a loopback GET-only endpoint."""

import json
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from trading_ecosystem.behavioral_research.contracts import canonical
from trading_ecosystem.behavioral_research.reports import validate


class ResearchServer(ThreadingHTTPServer):
    def __init__(self, output: Path, port: int = 8765) -> None:
        manifest = validate(output)
        data = (output / "behavior_research_packet.json").read_bytes()
        if sha256(data).hexdigest() != manifest["files"]["behavior_research_packet.json"]:
            raise ValueError("RESEARCH_PACKET_CHANGED_DURING_OPEN")
        self.research_status = json.loads(data)
        self.research_status.update(read_only=True, verification="VERIFIED_OFFLINE")
        super().__init__(("127.0.0.1", port), ResearchHandler)


class ResearchHandler(BaseHTTPRequestHandler):
    server: ResearchServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def respond(self, status: int, body: object) -> None:
        data = canonical(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.headers.get("Origin") is not None or self.headers.get("Host") not in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }:
            self.respond(403, {"error": "LOCAL_CLIENT_REQUIRED"})
        elif self.path != "/api/v1/behavior-research":
            self.respond(404, {"error": "OFFLINE_RESEARCH_ENDPOINT_ONLY"})
        else:
            self.respond(200, self.server.research_status)

    def do_POST(self) -> None:
        self.respond(405, {"error": "READ_ONLY"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST
