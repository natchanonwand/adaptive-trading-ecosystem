"""Installed transport through the real service and PostgreSQL, with a fake native boundary."""

import hashlib
import io
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, text

from tests.integration.test_baseline import migration, ready  # noqa: F401
from tests.phase5b_helpers import EA, report
from tests.test_phase5b_environment import binding
from tests.test_phase5b_installed_profile import complete_proof
from tests.test_phase5b_qualification import remanifest
from trading_ecosystem.tester import account_probe, process, qualification, readiness, store
from trading_ecosystem.tester.adapter import Blocked
from trading_ecosystem.tester.contracts import Run, State
from trading_ecosystem.tester.environment import TerminalBinding
from trading_ecosystem.tester.execution_plan import (
    plan_installed,
    selected_strategy,
    verify_account,
)
from trading_ecosystem.tester.installed_execution import InstalledExecutionAdapter
from trading_ecosystem.tester.research_account import AccountContext, ResearchAccountBinding
from trading_ecosystem.tester.service import Service


@pytest.fixture(scope="module")
def database(database: Engine) -> Iterator[Engine]:
    """Do not add this module's projects to the prior suite's paginated fixtures."""
    admin = create_engine(database.url.set(database="postgres"))
    name = "phase1_test_" + uuid4().hex
    isolated = create_engine(database.url.set(database=name))
    created = False
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        environment = dict(os.environ)
        environment["TE_DATABASE_URL"] = isolated.url.render_as_string(hide_password=False)
        migrated = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=environment,
            capture_output=True,
            check=False,
        )
        assert migrated.returncode == 0, "Isolated test migration failed; driver details suppressed"
        yield isolated
    finally:
        isolated.dispose()
        if created:
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def fixture(
    database: Engine,
    tmp: Path,
) -> tuple[Run, TerminalBinding, Path, dict[str, Any], AccountContext]:
    run = ready(database, tmp / "artifacts", "UNKNOWN", "UNKNOWN")
    terminal = binding(tmp)
    (tmp / "phase5_b1e").mkdir()
    proof = complete_proof(tmp / "phase5_b1e/probe", terminal)
    installed = terminal.terminal_data_root / "MQL5/Experts/Market/synthetic.ex5"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(EA)
    account = json.loads((proof / "account-binding.json").read_bytes())
    login = 31415926  # Synthetic test identifier, never a real account.
    account["account_fingerprint"] = hashlib.sha256(
        UUID(account["account_binding_id"]).bytes + str(login).encode()
    ).hexdigest()
    assessment = json.loads((proof / "assessment.json").read_bytes())
    assessment["account_binding"] = account
    (proof / "account-binding.json").write_text(json.dumps(account))
    (proof / "assessment.json").write_text(json.dumps(assessment))
    remanifest(proof)
    with database.begin() as conn:
        readiness.attest(
            conn,
            run.config.project_id,
            readiness.Authorization(
                event_id=uuid4(),
                previous_event_id=run.authorization_event_id,
                provenance="MARKETPLACE_AUTHORIZED",
                source_reference="Synthetic fixture",
                source_label="Synthetic fixture",
                authorization_basis="Synthetic regression only",
                confirmed=True,
            ),
        )
        run = store.create(conn, run.config.model_copy(update={"baseline_run_id": uuid4()}))
        assert run.config.configuration_id is not None
        record = qualification.qualify(
            conn,
            tmp / "artifacts",
            run.config.project_id,
            run.candidate_id,
            run.config.configuration_id,
            terminal,
            proof,
            Path(".local/phase5_b1g/synthetic").resolve(),
            installed_profile=True,
        )
    assert record["status"] == "CANDIDATE_EXECUTION_READY"
    context = AccountContext(ResearchAccountBinding.model_validate(account), login, 123)
    return run, terminal, proof, record, context


@pytest.mark.parametrize(
    "case",
    [
        "accepted",
        "candidate",
        "artifact",
        "config",
        "terminal",
        "account",
        "real",
        "traversal",
        "absolute",
        "same_name",
        "authorization",
        "unsupported",
        "tamper",
    ],
)
def test_plan_identity_and_fail_closed(
    database: Engine,
    tmp_path: Path,
    case: str,
) -> None:
    run, terminal, proof, record, context = fixture(database, tmp_path)
    installed = terminal.terminal_data_root / "MQL5/Experts/Market/synthetic.ex5"
    expected = State.BLOCKED_CANDIDATE_PROFILE_MISMATCH
    if case == "candidate":
        run = run.model_copy(update={"candidate_id": uuid4()})
        expected = State.BLOCKED_AUTHORIZATION_PROVENANCE
    elif case == "artifact":
        run = run.model_copy(update={"ea_sha256": "0" * 64})
        expected = State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH
    elif case == "config":
        run = run.model_copy(
            update={"config": run.config.model_copy(update={"timeout_seconds": 601})}
        )
        expected = State.BASELINE_CONFIGURATION_IDENTITY_MISMATCH
    elif case == "terminal":
        terminal = terminal.model_copy(update={"terminal_binding_id": uuid4()})
        expected = State.BLOCKED_TERMINAL_IDENTITY_MISMATCH
    elif case == "same_name":
        installed.write_bytes(b"wrong candidate")
        expected = State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH
    elif case in {"traversal", "absolute", "tamper"}:
        record["execution_binding"]["content"]["expert_reference"] = (
            "../escape.ex5" if case == "traversal" else "C:\\escape.ex5"
        )
        if case != "tamper":
            record["execution_binding"]["identity"] = qualification.digest(
                record["execution_binding"]["content"]
            )
    elif case == "authorization":
        run = run.model_copy(update={"authorization_event_id": uuid4()})
        expected = State.BLOCKED_AUTHORIZATION_PROVENANCE
    elif case == "unsupported":
        with database.begin() as conn:
            readiness.attest(
                conn,
                run.config.project_id,
                readiness.Authorization(
                    event_id=uuid4(),
                    previous_event_id=run.authorization_event_id,
                    provenance="OTHER_EXPLICIT_AUTHORIZATION",
                    source_reference="Synthetic",
                    source_label="Synthetic",
                    authorization_basis="Synthetic",
                    confirmed=True,
                ),
            )
            event = readiness.history(conn, run.config.project_id)[-1]
        run = run.model_copy(update={"authorization_event_id": UUID(event["event_id"])})
        expected = State.BLOCKED_CANDIDATE_INGESTION_MODEL
    with database.connect() as conn:

        def make() -> Any:
            return plan_installed(
                conn, tmp_path / "artifacts", run, record, terminal, proof, tmp_path / "output"
            )

        if case not in {"accepted", "account", "real"}:
            with pytest.raises(Blocked) as error:
                make()
            assert error.value.status == expected
            return
        plan = make()
        assert plan == make() and plan.identity == make().identity
    assert plan.timeout_seconds == 600
    assert "Expert=Market\\synthetic.ex5\n" in plan.native_config
    assert "Optimization=0\n" in plan.native_config and "ForwardMode=0\n" in plan.native_config
    assert Path(plan.report_path) == terminal.terminal_data_root / (
        run.config.baseline_run_id.hex + ".htm"
    )
    with pytest.raises(ValueError):
        plan.timeout_seconds = 601
    if case == "account":
        context = AccountContext(context.binding, context.login + 1, context.process_id)
        expected = State.BLOCKED_TESTER_ACCOUNT_UNBOUND
    elif case == "real":
        context = AccountContext(
            context.binding.model_copy(update={"environment_classification": "REAL"}),
            context.login,
            context.process_id,
        )
        expected = State.BLOCKED_TESTER_ACCOUNT_NOT_DEMO
    if case != "accepted":
        with pytest.raises(Blocked) as error:
            verify_account(plan, context)
        assert error.value.status == expected
    else:
        verify_account(plan, context)


@pytest.mark.parametrize(
    "mode",
    [
        "complete",
        "timeout",
        "timeout_bad_report",
        "cancelled",
        "license",
        "hash_changed",
        "account_changed",
    ],
)
def test_service_installed_transport_no_candidate_copy(
    database: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    run, terminal, proof, record, context = fixture(database, tmp_path)
    root = tmp_path / "phase5_b"
    root.mkdir()
    (root / "terminal-binding.json").write_text(terminal.model_dump_json())
    qualified = tmp_path / "phase5_b1g"
    qualified.mkdir()
    (qualified / "qualification.json").write_text(json.dumps(record))
    installed = terminal.terminal_data_root / "MQL5/Experts/Market/synthetic.ex5"
    original = installed.read_bytes()
    launches: list[str] = []

    def discover(_: TerminalBinding) -> AccountContext:
        if mode == "hash_changed":
            installed.write_bytes(b"changed before launch")
        return AccountContext(context.binding, context.login + (mode == "account_changed"), 123)

    monkeypatch.setattr("trading_ecosystem.tester.research_account.discover", discover)
    monkeypatch.setattr(account_probe, "restrict_runtime", lambda _: None)
    monkeypatch.setattr(account_probe, "close_session", lambda *_: None)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Candidate copy is forbidden")

    monkeypatch.setattr("shutil.copy2", forbidden)
    monkeypatch.setattr("shutil.copyfile", forbidden)

    def native(
        exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event, observer: Any = None
    ) -> process.Outcome:
        launches.append("FAKE_PROCESS_ONLY")
        assert exe == terminal.terminal_executable and cwd == exe.parent and timeout == 600
        assert len(args) == 1 and args[0].startswith("/config:")
        ini = Path(args[0].removeprefix("/config:"))
        text = ini.read_text()
        assert "Expert=Market\\synthetic.ex5" in text and "Optimization=0" in text
        assert not list(root.rglob("*.ex5"))
        logs = terminal.terminal_data_root / "logs"
        logs.mkdir(exist_ok=True)
        (logs / "synthetic.log").write_text(
            "invalid license" if mode == "license" else "100% real ticks"
        )
        (terminal.terminal_data_root / (run.config.baseline_run_id.hex + ".htm")).write_bytes(
            b"\xff" if mode == "timeout_bad_report" else report("synthetic")
        )
        return process.Outcome(
            0, timed_out=mode.startswith("timeout"), cancelled=mode == "cancelled"
        )

    monkeypatch.setattr(process, "execute", native)
    with database.begin() as conn:
        store.advance(conn, run.config.baseline_run_id, State.QUEUED)
    service = Service(database, tmp_path / "artifacts", root)
    service.worker(run.config.baseline_run_id, io.BytesIO())
    with database.connect() as conn:
        result = store.get(conn, run.config.baseline_run_id)
        normalized = store.result(conn, run.config.baseline_run_id)
    expected = {
        "complete": State.COMPLETE,
        "timeout": State.TIMEOUT,
        "timeout_bad_report": State.TIMEOUT,
        "cancelled": State.CANCELLED,
        "license": State.BLOCKED_LICENSE,
        "hash_changed": State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH,
        "account_changed": State.BLOCKED_TESTER_ACCOUNT_UNBOUND,
    }[mode]
    assert result.status == expected
    assert len(launches) == (0 if mode in {"hash_changed", "account_changed"} else 1)
    assert (normalized is not None) == (mode == "complete")
    assert result.declared_license_status == result.declared_tester_access == "UNKNOWN"
    assert not list(root.rglob("*.ex5")) and not list(root.rglob("native-account.ini"))
    if mode != "hash_changed":
        assert installed.read_bytes() == original
    plan_files = list(root.rglob("execution-plan.json"))
    assert len(plan_files) == 1
    assert str(context.login) not in plan_files[0].read_text()


def test_portable_dispatch(database: Engine, tmp_path: Path) -> None:
    run = ready(database, tmp_path)
    with database.connect() as conn:
        assert selected_strategy(conn, run) == "PORTABLE_ARTIFACT"


@pytest.mark.parametrize("case", ["plan_changed", "attempt_consumed"])
def test_persisted_plan_cannot_change_or_retry(
    database: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    run, terminal, proof, record, _ = fixture(database, tmp_path)
    root = tmp_path / "output"
    root.mkdir()
    binding_file = tmp_path / "binding.json"
    binding_file.write_text(terminal.model_dump_json())
    qualification_file = tmp_path / "qualification.json"
    qualification_file.write_text(json.dumps(record))
    adapter = InstalledExecutionAdapter(
        database, tmp_path / "artifacts", run, binding_file, qualification_file, proof
    )
    runtime = adapter.prepare(run.config, b"", run.ea_sha256, root, terminal.broker_name, Event())

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Must stop before account discovery or process creation")

    monkeypatch.setattr("trading_ecosystem.tester.research_account.discover", forbidden)
    monkeypatch.setattr(process, "execute", forbidden)
    if case == "plan_changed":
        (root / "execution-plan.json").write_text("{}")
    else:
        (root / "native-launch.json").write_text("{}")
    with pytest.raises(Blocked) as error:
        adapter.run(run.config, root, runtime, Event())
    assert error.value.status == State.BLOCKED_CANDIDATE_PROFILE_MISMATCH
