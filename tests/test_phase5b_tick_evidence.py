"""Synthetic semantic evidence and immutable offline reconciliation contracts."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from tests.phase5b_helpers import config, report
from trading_ecosystem.tester import evidence, reconciliation
from trading_ecosystem.tester.contracts import Run, State, transition
from trading_ecosystem.tester.execution_plan import CandidateExecutionPlan
from trading_ecosystem.tester.parser import parse
from trading_ecosystem.tester.tick_evidence import Coverage, extract

MODEL = "EVERY_TICK_BASED_ON_REAL_TICKS"


def test_deals_column_headers_are_not_duplicate_settings() -> None:
    raw = report("fixture") + b"<table><tr><td>Time</td><td>Symbol</td><td>Type</td></tr></table>"
    parsed = parse(raw, uuid4(), uuid4(), uuid4())
    assert parsed.metadata["Symbol"] == "XAUUSDm"
    with pytest.raises(ValueError, match="DUPLICATE_REPORT_FIELD"):
        parse(raw + b"<tr><td>Symbol:</td><td>XAUUSDm</td></tr>", uuid4(), uuid4(), uuid4())


@pytest.mark.parametrize(
    "log,html,expected,percentage",
    [
        ("Model=4", "", Coverage.UNVERIFIED, None),
        ("generating based on real ticks", "", Coverage.UNVERIFIED, None),
        ("", "History Quality:</td><td>100%", Coverage.UNVERIFIED, None),
        ("", "Modeling Quality:</td><td>100%", Coverage.UNVERIFIED, None),
        ("", "History Quality:</td><td><b>100% real ticks</b>", Coverage.VERIFIED, "100"),
        ("", "Real ticks:</td><td>100%", Coverage.VERIFIED, "100"),
        ("", "Real Tick Coverage:</td><td>99.25%", Coverage.PARTIAL, "99.25"),
        ("", "Real ticks (%):</td><td>0%", Coverage.PARTIAL, "0"),
        ("99.9% real ticks", "", Coverage.PARTIAL, "99.9"),
        ("100% real ticks", "", Coverage.VERIFIED, "100"),
        ("real ticks unavailable", "", Coverage.UNAVAILABLE, None),
        ("real ticks absent", "", Coverage.UNAVAILABLE, None),
        ("generated ticks substituted", "", Coverage.PARTIAL, None),
        ("100% real ticks; generated ticks", "", Coverage.UNVERIFIED, "100"),
        ("100% real ticks\n50% real ticks", "", Coverage.UNVERIFIED, None),
        ("100% real ticks\nreal ticks unavailable", "", Coverage.UNVERIFIED, "100"),
        ("", "Real ticks:</td><td>101%", Coverage.UNVERIFIED, None),
        ("Test passed", "", Coverage.UNVERIFIED, None),
    ],
)
def test_distinct_facts(log: str, html: str, expected: Coverage, percentage: str | None) -> None:
    result = extract(MODEL, log, ("<table><tr><td>" + html + "</td></tr></table>").encode())
    assert result.requested_model == MODEL
    assert result.classification == expected
    actual = result.real_tick_coverage_percentage
    assert (str(actual) if actual is not None else None) == percentage
    assert (result.full_real_tick_requirement == "PASS") == (expected == Coverage.VERIFIED)


def test_build6230_cells_counts_and_history_are_separate() -> None:
    html = b"""<table><tr><td>History Quality:</td><td><b>100% real ticks</b></td></tr>
    <tr><td>Bars:</td><td>34651</td><td>Ticks:</td><td>53200842</td></tr>
    <tr><td>Period:</td><td>M5 (2026.01.01 - 2026.06.30)</td></tr></table>"""
    result = extract(MODEL, "generating based on real ticks\nTest passed", html)
    assert result.classification == Coverage.VERIFIED
    assert result.coverage_source == ("REPORT:history quality",)
    assert (result.bars_count, result.ticks_count) == (34651, 53200842)
    assert result.history_range_evidence == ("M5 (2026.01.01 - 2026.06.30)",)
    assert result.modeling_quality is None


def source(root: Path, run: Run | None = None, quality: str = "100% real ticks") -> Run:
    """A complete hand-authored evidence fixture; no SDK or process is involved."""
    if run is None:
        run = Run(
            config=config(),
            candidate_id=uuid4(),
            artifact_id=uuid4(),
            ea_sha256="a" * 64,
            input_sha256=None,
            declared_license_status="UNKNOWN",
            declared_tester_access="UNKNOWN",
            status=State.BLOCKED_REAL_TICKS_UNAVAILABLE,
            exit_code=0,
            created_at=datetime.now(UTC),
        )
    root.mkdir()
    raw = report("fixture").replace(b"<td>100%</td>", f"<td>{quality}</td>".encode())
    (root / "report.htm").write_bytes(raw)
    (root / "tester-sanitized.log").write_text("generating based on real ticks\nTest passed")
    plan = CandidateExecutionPlan(
        baseline_run_id=run.config.baseline_run_id,
        candidate_id=run.candidate_id,
        project_id=run.config.project_id,
        configuration_id=run.config.configuration_id or uuid4(),
        configuration_identity="b" * 64,
        qualification_identity="c" * 64,
        artifact_sha256=run.ea_sha256,
        expert_reference="fixture.ex5",
        terminal_binding_json="{}",
        account_binding_json="{}",
        native_config="Model=4",
        native_config_sha256="d" * 64,
        report_path=str(root / "report.htm"),
        evidence_root=str(root),
        timeout_seconds=600,
    )
    if run.config.configuration_id is None:
        run = run.model_copy(
            update={
                "config": run.config.model_copy(update={"configuration_id": plan.configuration_id})
            }
        )
    evidence.write_json(root / "configuration.json", run.model_dump(mode="json"))
    evidence.write_json(
        root / "execution-plan.json",
        {"identity": plan.identity, "content": plan.model_dump(mode="json")},
    )
    evidence.write_json(
        root / "execution-strategy.json", {"execution_strategy": "INSTALLED_PROFILE_REFERENCE"}
    )
    evidence.write_json(
        root / "native-report-origin.json", {"raw_sha256": hashlib.sha256(raw).hexdigest()}
    )
    evidence.write_json(
        root / "native-cleanup.json",
        {
            "processes": [
                {"role": role, "identity_verified": True, "exit_code": 0}
                for role in ("terminal", "tester")
            ]
        },
    )
    identity = evidence.finalize(root, run.status.value)
    return run.model_copy(update={"evidence_identity": identity})


def assess(root: Path, run: Run) -> dict[str, Any]:
    return reconciliation.assess(
        root, run, str(run.evidence_identity), evidence.file_identity(root / "report.htm")
    )


def test_offline_parse_provenance_and_immutable_outcome(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = source(root)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    record = assess(root, run)
    assert record["reconciled_assessment"] == Coverage.VERIFIED
    assert record["execution_outcome"] == State.BLOCKED_REAL_TICKS_UNAVAILABLE
    assert record["normalization_provenance"] == "POST_RUN_OFFLINE_RECONCILIATION"
    assert record["offline_normalization"]["metrics"]["total_trades"] == 10
    assert record["offline_normalization"]["baseline_run_id"] == str(run.config.baseline_run_id)
    assert record["baseline_result_created"] is False and record["new_execution_attempts"] == 0
    reconciliation.persist(tmp_path / "derived", record)
    assert json.loads((tmp_path / "derived/assessment.json").read_bytes()) == record
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}
    with pytest.raises(ValueError, match="INVALID_BASELINE_TRANSITION"):
        transition(run.status, State.COMPLETE)
    with pytest.raises(FileExistsError):
        reconciliation.persist(tmp_path / "derived", record)


@pytest.mark.parametrize("quality", ["100%", "50% real ticks", "UNKNOWN"])
def test_no_parser_recovery_without_coverage(
    tmp_path: Path, quality: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "run"
    run = source(root, quality=quality)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Parser must not run without full real-tick proof")

    monkeypatch.setattr(reconciliation, "parse", forbidden)
    assert assess(root, run)["offline_normalization"] is None


@pytest.mark.parametrize("name", ["report.htm", "tester-sanitized.log", "execution-plan.json"])
def test_evidence_tampering_fails(tmp_path: Path, name: str) -> None:
    root = tmp_path / "run"
    run = source(root)
    with (root / name).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        assess(root, run)


def test_no_synthetic_metrics_on_invalid_report(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = source(root)
    raw = (root / "report.htm").read_bytes().replace(b"Total Net Profit", b"Missing field")
    (root / "report.htm").write_bytes(raw)
    manifest = json.loads((root / "manifest.json").read_bytes())
    origin = {"raw_sha256": hashlib.sha256(raw).hexdigest()}
    (root / "native-report-origin.json").write_text(json.dumps(origin))
    for name in ("report.htm", "native-report-origin.json"):
        manifest["files"][name] = evidence.file_identity(root / name)
    manifest.pop("identity")
    identity = reconciliation.digest(manifest)
    (root / "manifest.json").write_text(json.dumps({**manifest, "identity": identity}))
    record = assess(root, run.model_copy(update={"evidence_identity": identity}))
    assert record["diagnostic"] == "OFFLINE_REPORT_VALIDATION_FAILED"
    assert record["offline_normalization"] is None
