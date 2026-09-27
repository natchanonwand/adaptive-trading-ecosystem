"""Fresh PostgreSQL plus real adapter staging with a synthetic process boundary."""

import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path
from threading import Event, Thread
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from tests.phase5b_helpers import EA, config, environment, report
from trading_ecosystem.tester import store
from trading_ecosystem.tester.adapter import Adapter
from trading_ecosystem.tester.api import BaselineServer
from trading_ecosystem.tester.contracts import Run, State
from trading_ecosystem.tester.process import Outcome
from trading_ecosystem.tester.service import Busy, Service
from trading_ecosystem.workbench import store as onboarding
from trading_ecosystem.workbench.contracts import Binding, CandidateInput, CreateProject, SourceType


@pytest.fixture(scope="module", autouse=True)
def migration(database: Engine) -> None:
    env = dict(os.environ)
    env["TE_DATABASE_URL"] = database.url.render_as_string(hide_password=False)
    for name in ("workbench", "baseline", "baseline"):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", f"alembic-{name}.ini", "upgrade", "head"],
            env=env,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, (
            "Baseline migration failed (private driver details suppressed)"
        )
    with database.connect() as conn:
        assert (
            conn.execute(
                text("SELECT version_num FROM workbench.baseline_alembic_version")
            ).scalar_one()
            == "0001_baselines"
        )
        assert (
            conn.execute(text("SELECT version_num FROM workbench.alembic_version")).scalar_one()
            == "0001_projects"
        )
        assert (
            conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
            == "0001_journal"
        )


def ready(
    database: Engine,
    root: Path,
    license_status: str = "USER_ATTESTED",
    access: str = "USER_CONFIRMED",
) -> Run:
    with database.begin() as conn:
        artifact = onboarding.register_artifact(conn, root, "synthetic.ex5", "EA", EA)
        project = onboarding.create_project(
            conn,
            root,
            CreateProject.model_validate(
                dict(
                    project_id=uuid4(),
                    project_name="Synthetic tester fixture",
                    source_type=SourceType.EXTERNAL_EA,
                    candidate=CandidateInput.model_validate(
                        dict(
                            artifact_id=artifact.artifact_id,
                            license_status=license_status,
                            tester_access_status=access,
                        )
                    ),
                    broker_binding=Binding(
                        broker_name="Synthetic demo",
                        canonical_asset="XAUUSD",
                        broker_symbol="XAUUSDm",
                        timeframe="H1",
                        symbol_confirmed=True,
                    ),
                )
            ),
        )
        return store.create(conn, config(project_id=project.project_id))


def simulated(
    mode: str, started: Event | None = None, release: Event | None = None
) -> Callable[[Path, list[str], Path, float, Event], Outcome]:
    def process(exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event) -> Outcome:
        assert args[0] == "/portable" and args[1].startswith("/config:")
        assert timeout == 600 and exe == cwd / "terminal64.exe"
        expert = next((cwd / "MQL5/Experts").glob("*.ex5")).stem
        assert (cwd / "MQL5/Experts" / (expert + ".ex5")).read_bytes() == EA
        if started:
            started.set()
        if release:
            while not release.wait(0.02):
                if cancel.is_set():
                    return Outcome(None, cancelled=True)
        logs = cwd / "logs"
        logs.mkdir()
        value = {
            "license": "invalid license",
            "access": "testing prohibited",
            "init": "initialization failed",
            "ticks": "real ticks unavailable",
        }.get(mode, "100% real ticks")
        (logs / "tester.log").write_text(value, encoding="utf-8")
        if mode == "timeoutlogs":
            (logs / "tester.log").write_bytes(b"x" * (9 * 1024 * 1024))
        raw = report(expert)
        if mode == "parse":
            raw = b"not a report"
        if mode == "mismatch":
            raw = raw.replace(b"XAUUSDm", b"BTCUSDm")
        if mode != "missing":
            (cwd / (expert + ".htm")).write_bytes(raw)
        return Outcome(5 if mode == "exit" else 0, timed_out=mode in {"timeout", "timeoutlogs"})

    return process


def finish(service: Service, run_id: UUID) -> Run:
    service.start(run_id)
    assert service.thread is not None
    service.thread.join(timeout=15)
    assert not service.thread.is_alive()
    with service.engine.connect() as conn:
        return store.get(conn, run_id)


def test_success_persistence_identity_and_no_retry(database: Engine, tmp_path: Path) -> None:
    run = ready(database, tmp_path / "artifacts")
    cfg = run.config
    service = Service(
        database,
        tmp_path / "artifacts",
        tmp_path / "evidence",
        Adapter(environment(tmp_path), simulated("success")),
    )
    result_run = finish(service, cfg.baseline_run_id)
    assert result_run.status == State.COMPLETE
    assert result_run.history == (
        State.READY,
        State.QUEUED,
        State.PREPARING,
        State.RUNNING,
        State.PARSING,
        State.COMPLETE,
    )
    assert result_run.observed_tester_status == "SUCCESS"
    assert result_run.declared_tester_access == "USER_CONFIRMED"
    with database.begin() as conn:
        result = store.result(conn, cfg.baseline_run_id)
        assert result is not None
        assert result.project_id == cfg.project_id and result.candidate_id == run.candidate_id
        assert result.result_identity == result_run.result_identity
        assert store.create(conn, cfg) == result_run
        with pytest.raises(ValueError, match="IMMUTABLE"):
            store.create(conn, cfg.model_copy(update={"leverage": 200}))
    root = service.root / "runs" / str(cfg.project_id) / str(cfg.baseline_run_id)
    import hashlib

    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["identity"] == result_run.evidence_identity
    for name, sha in manifest["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == sha
    before = (root / "manifest.json").read_bytes()
    with pytest.raises(ValueError):
        service.start(cfg.baseline_run_id)
    assert before == (root / "manifest.json").read_bytes()


@pytest.mark.parametrize(
    "mode,status",
    [
        ("license", State.BLOCKED_LICENSE),
        ("access", State.BLOCKED_TESTER_ACCESS),
        ("init", State.INITIALIZATION_FAILED),
        ("ticks", State.BLOCKED_REAL_TICKS_UNAVAILABLE),
        ("timeout", State.TIMEOUT),
        ("timeoutlogs", State.TIMEOUT),
        ("missing", State.REPORT_MISSING),
        ("parse", State.REPORT_PARSE_FAILED),
        ("mismatch", State.REPORT_PARSE_FAILED),
        ("exit", State.TESTER_FAILED),
    ],
)
def test_failures_never_produce_result(
    database: Engine, tmp_path: Path, mode: str, status: State
) -> None:
    run = ready(database, tmp_path / "artifacts")
    service = Service(
        database,
        tmp_path / "artifacts",
        tmp_path / "evidence",
        Adapter(environment(tmp_path), simulated(mode)),
    )
    final = finish(service, run.config.baseline_run_id)
    assert final.status == status
    assert final.evidence_identity and final.completed_at and final.started_at
    with database.connect() as conn:
        assert store.result(conn, run.config.baseline_run_id) is None


@pytest.mark.parametrize(
    "problem,status",
    [
        ("changed", State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH),
        ("missing", State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH),
        ("license", State.BLOCKED_LICENSE),
        ("access", State.BLOCKED_TESTER_ACCESS),
    ],
)
def test_preflight_never_launches(
    database: Engine, tmp_path: Path, problem: str, status: State
) -> None:
    run = ready(
        database,
        tmp_path / "artifacts",
        "NOT_AUTHORIZED" if problem == "license" else "USER_ATTESTED",
        "UNAVAILABLE" if problem == "access" else "USER_CONFIRMED",
    )
    with database.connect() as conn:
        artifact = onboarding.get_artifact(conn, run.artifact_id)
    path = onboarding.artifact_path(tmp_path / "artifacts", artifact)
    if problem == "changed":
        path.write_bytes(b"substitution")
    if problem == "missing":
        path.unlink()
    service = Service(database, tmp_path / "artifacts", tmp_path / "evidence")
    assert finish(service, run.config.baseline_run_id).status == status


@pytest.mark.parametrize(
    "mode,state,observed",
    [
        ("success", State.COMPLETE, "SUCCESS"),
        ("license", State.BLOCKED_LICENSE, "LICENSE_BLOCKED"),
        ("access", State.BLOCKED_TESTER_ACCESS, "TESTER_ACCESS_BLOCKED"),
        ("init", State.INITIALIZATION_FAILED, "INITIALIZATION_FAILED"),
    ],
)
def test_unknown_declarations_are_preserved_after_simulated_observation(
    database: Engine,
    tmp_path: Path,
    mode: str,
    state: State,
    observed: str,
) -> None:
    run = ready(database, tmp_path / "artifacts", "UNKNOWN", "UNKNOWN")
    assert run.status == State.READY and run.observed_tester_status == "UNKNOWN"
    started = Event()
    service = Service(
        database,
        tmp_path / "artifacts",
        tmp_path / "evidence",
        Adapter(environment(tmp_path), simulated(mode, started)),
    )
    final = finish(service, run.config.baseline_run_id)
    assert started.is_set()  # Synthetic process callable only; never native MT5/EX5.
    assert final.status == state and final.observed_tester_status == observed
    assert final.declared_license_status == final.declared_tester_access == "UNKNOWN"
    with database.connect() as conn:
        candidate = onboarding.get_candidate(conn, run.candidate_id)
        assert candidate.license_status == candidate.tester_access_status == "UNKNOWN"


def test_single_active_and_cancel(database: Engine, tmp_path: Path) -> None:
    run = ready(database, tmp_path / "artifacts")
    started, release = Event(), Event()
    root = tmp_path / "evidence"
    service = Service(
        database,
        tmp_path / "artifacts",
        root,
        Adapter(environment(tmp_path), simulated("success", started, release)),
    )
    other = Service(database, tmp_path / "artifacts", root)
    try:
        service.start(run.config.baseline_run_id)
        assert started.wait(10)
        with pytest.raises(Busy):
            service.start(run.config.baseline_run_id)
        with pytest.raises(Busy):
            other.start(run.config.baseline_run_id)
        with pytest.raises(Busy):
            other.cancel(run.config.baseline_run_id)
        service.cancel(run.config.baseline_run_id)
        assert service.thread is not None
        service.thread.join(timeout=10)
        with database.connect() as conn:
            assert store.get(conn, run.config.baseline_run_id).status == State.CANCELLED
            assert store.result(conn, run.config.baseline_run_id) is None
    finally:
        release.set()
        service.close()


def test_interrupted_run_is_never_restarted(database: Engine, tmp_path: Path) -> None:
    run = ready(database, tmp_path)
    with database.begin() as conn:
        store.advance(conn, run.config.baseline_run_id, State.QUEUED)
        store.advance(conn, run.config.baseline_run_id, State.PREPARING)
    service = Service(database, tmp_path, tmp_path / "evidence")
    with pytest.raises(ValueError):
        service.start(run.config.baseline_run_id)
    with database.connect() as conn:
        failed = store.get(conn, run.config.baseline_run_id)
        assert failed.status == State.TESTER_FAILED
        assert "INTERRUPTED_OWNER" in failed.diagnostic
    assert service.thread is None


def test_restart_recovery_preserves_partial_evidence(database: Engine, tmp_path: Path) -> None:
    run = ready(database, tmp_path)
    root = tmp_path / "evidence"
    partial = root / "runs" / str(run.config.project_id) / str(run.config.baseline_run_id)
    partial.mkdir(parents=True)
    (partial / "partial.log").write_bytes(b"immutable interrupted diagnostic")
    with database.begin() as conn:
        store.advance(conn, run.config.baseline_run_id, State.QUEUED)
    service = Service(database, tmp_path, root)
    service.recover()
    assert (partial / "partial.log").read_bytes() == b"immutable interrupted diagnostic"
    assert not (partial / "manifest.json").exists()
    with database.connect() as conn:
        assert store.get(conn, run.config.baseline_run_id).status == State.TESTER_FAILED


def test_cancel_cannot_race_committed_completion(
    database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trading_ecosystem.tester import evidence

    run = ready(database, tmp_path / "artifacts")
    service = Service(
        database,
        tmp_path / "artifacts",
        tmp_path / "evidence",
        Adapter(environment(tmp_path), simulated("success")),
    )
    reached, release, attempted, finished = Event(), Event(), Event(), Event()
    original = evidence.finalize
    errors: list[str] = []

    def finalize(root: Path, status: str) -> str:
        reached.set()
        assert release.wait(10)
        return original(root, status)

    def cancel() -> None:
        attempted.set()
        try:
            service.cancel(run.config.baseline_run_id)
        except ValueError as exc:
            errors.append(str(exc))
        finally:
            finished.set()

    monkeypatch.setattr(evidence, "finalize", finalize)
    service.start(run.config.baseline_run_id)
    assert reached.wait(10)
    thread = Thread(target=cancel)
    thread.start()
    try:
        assert attempted.wait(5)
        assert not finished.wait(0.05)
    finally:
        release.set()
        thread.join(timeout=10)
        assert service.thread is not None
        service.thread.join(timeout=10)
    assert errors == ["BASELINE_ALREADY_TERMINAL"]
    with database.connect() as conn:
        assert store.get(conn, run.config.baseline_run_id).status == State.COMPLETE
        assert store.result(conn, run.config.baseline_run_id) is not None


@contextmanager
def server(database: Engine, tmp_path: Path) -> Iterator[BaselineServer]:
    instance = BaselineServer(
        database, tmp_path, Path("dashboard/dist"), 0, root=tmp_path / "evidence"
    )
    thread = Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield instance
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=5)


def test_http_read_confirm_and_cross_origin_boundary(database: Engine, tmp_path: Path) -> None:
    run = ready(database, tmp_path)
    with server(database, tmp_path) as instance:
        connection = HTTPConnection("127.0.0.1", instance.server_port, timeout=10)
        base = "/workbench-api/baselines/" + str(run.config.baseline_run_id)
        connection.request("GET", base)
        response = connection.getresponse()
        assert response.status == 200 and json.loads(response.read())["run"]["status"] == "READY"
        headers = {"Content-Type": "application/json", "X-Workbench-Request": "1"}
        connection.request(
            "POST",
            base + "/start",
            json.dumps({"confirmed": True}),
            {**headers, "Origin": "https://external.invalid"},
        )
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.request("POST", base + "/start", "{}", headers)
        response = connection.getresponse()
        assert response.status == 400
        response.read()
        connection.request("POST", base + "/cancel", json.dumps({"confirmed": True}), headers)
        response = connection.getresponse()
        assert response.status == 200 and json.loads(response.read())["status"] == "CANCELLED"
        connection.close()
