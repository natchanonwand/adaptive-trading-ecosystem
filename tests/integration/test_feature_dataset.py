import json
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

import pytest

from tests.integration.test_external_observer import advance, fake
from tests.integration.test_external_observer import observer as observer
from tests.integration.test_monitoring import monitoring_migration as monitoring_migration
from tests.observer.fixtures import position, trade
from trading_ecosystem.features.api import FeatureServer
from trading_ecosystem.features.builder import build
from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.features.dataset import export, validate
from trading_ecosystem.observer.export import export_session
from trading_ecosystem.observer.runtime import Observer


@pytest.fixture
def recording(observer: Observer, tmp_path: Path) -> Path:
    assert advance(observer, 0)
    client = fake(observer)
    client.positions = (position(),)
    client.deals = (trade(1, 3),)
    assert advance(observer, 3)
    client.positions = ()
    client.deals += (trade(2, 6, type=1, entry=1, profit="5"),)
    assert advance(observer, 6)
    path = tmp_path / "source"
    with observer.engine.connect() as conn:
        export_session(conn, observer.session, path)
    return path


def test_export_rebuild_twice_raw_parity_and_source_not_changed(
    recording: Path, tmp_path: Path
) -> None:
    before = {p.name: p.read_bytes() for p in recording.iterdir()}
    one = export([recording], tmp_path / "one", BuildConfig())
    two = export([recording], tmp_path / "two", BuildConfig())
    assert one == two and validate(tmp_path / "one") == one
    for name in one["datasets"]:
        assert (tmp_path / "one" / (name + ".parquet")).read_bytes() == (
            tmp_path / "two" / (name + ".parquet")
        ).read_bytes()
    materialized, _ = build([recording], BuildConfig())
    raw, _ = build([recording], BuildConfig(), raw_replay=True)
    assert materialized == raw
    assert before == {p.name: p.read_bytes() for p in recording.iterdir()}


def test_config_identity_duplicate_sources_and_no_overwrite(
    recording: Path, tmp_path: Path
) -> None:
    one = export([recording, recording], tmp_path / "one", BuildConfig())
    two = export([recording], tmp_path / "two", BuildConfig(recent_quote_count=10))
    assert one["config_hash"] != two["config_hash"]
    assert one["datasets"]["episode_features"]["rows"] == 1
    with pytest.raises(ValueError, match="ALREADY_EXISTS"):
        export([recording], tmp_path / "one", BuildConfig())


@pytest.mark.parametrize(
    "tamper", ["parquet", "version", "source_hash", "provenance", "dataset_metadata"]
)
def test_export_tampering_rejected(recording: Path, tmp_path: Path, tamper: str) -> None:
    output = tmp_path / "features"
    manifest = export([recording], output, BuildConfig())
    if tamper == "parquet":
        with (output / "episode_features.parquet").open("ab") as handle:
            handle.write(b"tamper")
    else:
        if tamper == "version":
            manifest["feature_set_id"] = "changed"
        elif tamper == "provenance":
            manifest["dataset_type"] = "REAL_DEMO_OBSERVATION"
        elif tamper == "dataset_metadata":
            manifest["datasets"]["episode_features"]["config_hash"] = "changed"
        else:
            manifest["sources"][0]["source_manifest_hash"] = "changed"
        (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        validate(output)


def test_offline_feature_quality_api_read_only(recording: Path, tmp_path: Path) -> None:
    output = tmp_path / "features"
    export([recording], output, BuildConfig())
    with FeatureServer(output, 0) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for method, status, headers in (
                ("GET", 200, {}),
                ("POST", 405, {}),
                ("GET", 403, {"Origin": "https://example.com"}),
            ):
                client = HTTPConnection("127.0.0.1", server.server_port)
                client.request(method, "/api/v1/features", headers=headers)
                response = client.getresponse()
                body = json.loads(response.read())
                assert response.status == status
                if status == 200:
                    assert body["read_only"] and body["dataset_type"] == "SYNTHETIC_QUALIFICATION"
                client.close()
        finally:
            server.shutdown()
            worker.join(5)
