import hashlib
import json
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

import pytest

from tests.integration.test_external_observer import observer as observer
from tests.integration.test_feature_dataset import recording as recording
from tests.integration.test_monitoring import monitoring_migration as monitoring_migration
from trading_ecosystem.behavioral_research.__main__ import main
from trading_ecosystem.behavioral_research.api import ResearchServer
from trading_ecosystem.behavioral_research.contracts import ResearchConfig
from trading_ecosystem.behavioral_research.engine import research
from trading_ecosystem.behavioral_research.loader import load
from trading_ecosystem.behavioral_research.reports import export, validate
from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.features.dataset import export as feature_export


@pytest.fixture
def features(recording: Path, tmp_path: Path) -> Path:
    path = tmp_path / "features"
    feature_export([recording], path, BuildConfig())
    return path


def test_offline_export_twice_rebuild_hashes_and_preserve_sources(
    features: Path, tmp_path: Path
) -> None:
    before = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*.parquet")
    }
    first, second = tmp_path / "one", tmp_path / "two"
    a, b = export(features, first, ResearchConfig()), export(features, second, ResearchConfig())
    assert a["content_hash"] == b["content_hash"] and a["files"] == b["files"]
    assert validate(first) == a and validate(second) == b
    assert before == {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*.parquet")
    }
    assert json.loads((first / "research.json").read_bytes())["hypotheses"] == []
    with pytest.raises(ValueError, match="ALREADY_EXISTS"):
        export(features, first, ResearchConfig())


@pytest.mark.parametrize(
    "change", ["dataset_type", "feature_set_id", "rows", "primary_key", "source", "x_y"]
)
def test_invalid_phase4c_input_fails_closed(features: Path, change: str) -> None:
    path = features / "manifest.json"
    manifest = json.loads(path.read_bytes())
    if change in ("dataset_type", "feature_set_id"):
        manifest[change] = "REAL_DEMO_OBSERVATION" if change == "dataset_type" else "wrong"
    elif change == "rows":
        manifest["datasets"]["episode_features"]["rows"] += 1
    elif change == "source":
        manifest["session_ids"] = ["wrong"]
    else:
        # A modified table must fail regardless of attacker-updated file checksum.
        import pyarrow as pa
        import pyarrow.parquet as pq

        table_path = features / "episode_features.parquet"
        table = pq.read_table(table_path)
        if change == "primary_key":
            table = pa.concat_tables([table, table])
        else:
            table = table.append_column("net_observed_pnl", pa.array(["999"] * len(table)))
        pq.write_table(table, table_path)
        manifest["datasets"]["episode_features"]["sha256"] = hashlib.sha256(
            table_path.read_bytes()
        ).hexdigest()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        load(features, ResearchConfig())


@pytest.mark.parametrize("change", ["packet", "fingerprint", "manifest", "report"])
def test_research_export_tampering_rejected(features: Path, tmp_path: Path, change: str) -> None:
    output = tmp_path / "research"
    export(features, output, ResearchConfig())
    names = dict(
        packet="behavior_research_packet.json",
        fingerprint="behavior_fingerprint.json",
        manifest="manifest.json",
        report="report.md",
    )
    path = output / names[change]
    if change == "manifest":
        body = json.loads(path.read_bytes())
        body["dataset_type"] = "REAL_DEMO_OBSERVATION"
        path.write_text(json.dumps(body), encoding="utf-8")
    else:
        path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError):
        validate(output)


def test_selection_empty_and_real_label_not_fabricated(features: Path) -> None:
    result = research(features, ResearchConfig(candidate_id="not-present"))
    assert result["fingerprint"]["n"] == 0 and result["status"] == "SOFTWARE_VALIDATION_ONLY"
    source = load(features, ResearchConfig())
    candidate = source.episodes[0]["candidate_id"]
    assert len(load(features, ResearchConfig(candidate_id=candidate)).episodes) == 1


def test_offline_cli_validate_fingerprint_compare_and_report(
    features: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    for command in ("validate", "fingerprint", "compare", "report"):
        arguments = ["research", command, str(features)]
        if command == "compare":
            arguments += ["--right", str(features)]
        monkeypatch.setattr(sys, "argv", arguments)
        main()
        output = capsys.readouterr().out
        if command == "report":
            assert "NO REAL EA BEHAVIORAL CONCLUSIONS" in output
        else:
            assert isinstance(json.loads(output), dict)


def test_research_api_read_only_loopback_and_exact_endpoint(features: Path, tmp_path: Path) -> None:
    output = tmp_path / "research"
    export(features, output, ResearchConfig())
    with ResearchServer(output, 0) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            conn.request("GET", "/api/v1/behavior-research")
            response = conn.getresponse()
            body = json.loads(response.read())
            assert response.status == 200 and body["read_only"] is True
            assert body["status"] == "SOFTWARE_VALIDATION_ONLY"
            for method, route, headers, status in (
                ("POST", "/api/v1/behavior-research", {}, 405),
                ("GET", "/api/v1/behavior-research", {"Origin": "https://example.invalid"}, 403),
                ("GET", "/api/v1/behavior-research", {"Host": "example.invalid"}, 403),
                ("GET", "/api/v1/other", {}, 404),
            ):
                conn.request(method, route, headers=headers)
                response = conn.getresponse()
                response.read()
                assert response.status == status
            conn.close()
        finally:
            server.shutdown()
            worker.join(timeout=5)
