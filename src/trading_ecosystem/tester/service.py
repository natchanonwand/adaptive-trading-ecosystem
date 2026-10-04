"""One local execution at a time, immutable attempts, persisted failures and cancellation."""

import hashlib
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert

from trading_ecosystem.tester import evidence, store
from trading_ecosystem.tester.adapter import (
    Adapter,
    Blocked,
    load_environment,
    observed_failure,
    real_ticks_verified,
)
from trading_ecosystem.tester.contracts import ACTIVE, Run, State
from trading_ecosystem.tester.execution_plan import selected_strategy
from trading_ecosystem.tester.installed_execution import InstalledExecutionAdapter
from trading_ecosystem.tester.parser import decode_report, parse
from trading_ecosystem.workbench import store as onboarding


class Busy(ValueError):
    """Another local baseline owns the execution lock; no hidden queue/retry."""


class Service:
    def __init__(
        self, engine: Engine, artifacts: Path, root: Path, adapter: Adapter | None = None
    ) -> None:
        self.engine, self.artifacts, self.root, self.adapter = engine, artifacts, root, adapter
        self.guard = threading.Lock()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.active_id: UUID | None = None

    def acquire(self) -> BinaryIO:
        import msvcrt

        self.root.mkdir(parents=True, exist_ok=True)
        handle = (self.root / "active.lock").open("a+b")
        try:
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return handle
        except OSError:
            handle.close()
            raise Busy("BASELINE_TESTER_BUSY") from None

    def start(self, run_id: UUID) -> Run:
        with self.guard:
            if self.thread is not None and self.thread.is_alive():
                raise Busy("BASELINE_TESTER_BUSY")
            handle = self.acquire()
            try:
                with self.engine.begin() as conn:
                    # Free OS lock proves an earlier owner is gone. Never retry its partial run.
                    rows = conn.execute(select(store.runs.c.body)).scalars()
                    for body in rows:
                        previous = Run.model_validate(body)
                        if previous.status in ACTIVE:
                            store.advance(
                                conn,
                                previous.config.baseline_run_id,
                                State.TESTER_FAILED,
                                diagnostic="INTERRUPTED_OWNER; NO_AUTOMATIC_RETRY",
                            )
                with self.engine.begin() as conn:
                    from trading_ecosystem.tester.readiness import require_execution_contract

                    require_execution_contract(conn, store.get(conn, run_id).config)
                    queued = store.advance(conn, run_id, State.QUEUED)
                self.cancel_event = threading.Event()
                self.active_id = run_id
                self.thread = threading.Thread(
                    target=self.worker, args=(run_id, handle), daemon=True
                )
                self.thread.start()
                return queued
            except Exception:
                handle.close()
                raise

    def recover(self) -> None:
        """Mark abandoned states under the ownership lock without replaying any work."""
        try:
            handle = self.acquire()
        except Busy:
            return
        try:
            with self.engine.begin() as conn:
                for body in conn.execute(select(store.runs.c.body)).scalars():
                    previous = Run.model_validate(body)
                    if previous.status in ACTIVE:
                        store.advance(
                            conn,
                            previous.config.baseline_run_id,
                            State.TESTER_FAILED,
                            diagnostic="INTERRUPTED_OWNER; NO_AUTOMATIC_RETRY",
                        )
        finally:
            handle.close()

    def cancel(self, run_id: UUID) -> Run:
        with self.guard:
            with self.engine.connect() as conn:
                current = store.get(conn, run_id)
            if current.status not in ACTIVE | {State.READY}:
                raise ValueError("BASELINE_ALREADY_TERMINAL")
            if self.active_id == run_id and self.thread is not None and self.thread.is_alive():
                self.cancel_event.set()
                with self.engine.connect() as conn:
                    return store.get(conn, run_id)
            if current.status in ACTIVE:
                raise Busy("BASELINE_OWNED_BY_ANOTHER_PROCESS")
            with self.engine.begin() as conn:
                return store.advance(
                    conn, run_id, State.CANCELLED, diagnostic="CANCELLED_BEFORE_START"
                )

    def advance(self, run_id: UUID, state: State, **changes: object) -> Run:
        with self.engine.begin() as conn:
            return store.advance(conn, run_id, state, **changes)

    def worker(self, run_id: UUID, handle: BinaryIO) -> None:
        root: Path | None = None
        runtime: Path | None = None
        run: Run | None = None
        exit_code: int | None = None
        observed = "UNKNOWN"
        try:
            run = self.advance(run_id, State.PREPARING)
            root = self.root / "runs" / str(run.config.project_id) / str(run_id)
            root.mkdir(parents=True, exist_ok=False)
            evidence.write_json(root / "configuration.json", run.model_dump(mode="json"))
            if run.declared_license_status == "NOT_AUTHORIZED":
                raise Blocked(State.BLOCKED_LICENSE)
            if run.declared_tester_access == "UNAVAILABLE":
                raise Blocked(State.BLOCKED_TESTER_ACCESS)
            with self.engine.connect() as conn:
                from trading_ecosystem.tester.readiness import require_execution_contract

                try:
                    require_execution_contract(conn, run.config)
                except ValueError:
                    raise Blocked(State.BLOCKED_AUTHORIZATION_PROVENANCE) from None
                p = store.project(conn, run.config.project_id)
                try:
                    artifact = onboarding.get_artifact(conn, run.artifact_id)
                except ValueError:
                    raise Blocked(State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH) from None
                execution_strategy = selected_strategy(conn, run)
            if artifact.sha256 != run.ea_sha256 or not onboarding.verify_artifact(
                self.artifacts, artifact
            ):
                raise Blocked(State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH)
            ea = b""
            if execution_strategy == "INSTALLED_PROFILE_REFERENCE":
                adapter: Adapter = InstalledExecutionAdapter(
                    self.engine,
                    self.artifacts,
                    run,
                    self.root / "terminal-binding.json",
                    self.root.parent / "phase5_b1g/qualification.json",
                    self.root.parent / "phase5_b1e/probe",
                )
            else:
                try:
                    ea = onboarding.artifact_path(self.artifacts, artifact).read_bytes()
                except OSError:
                    raise Blocked(State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH) from None
                adapter = self.adapter or Adapter(
                    load_environment(self.root / "environment.json", run.config.symbol)
                )
            evidence.write_json(
                root / "execution-strategy.json",
                {
                    "execution_strategy": execution_strategy,
                    "candidate_id": str(run.candidate_id),
                    "authorization_event_id": str(run.authorization_event_id),
                },
            )
            runtime = adapter.prepare(
                run.config, ea, run.ea_sha256, root, p.broker_binding.broker_name, self.cancel_event
            )
            if execution_strategy == "PORTABLE_ARTIFACT":
                staged = runtime / "MQL5" / "Experts" / (run_id.hex + ".ex5")
                if hashlib.sha256(staged.read_bytes()).hexdigest() != run.ea_sha256:
                    raise Blocked(State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH)
                evidence.write_json(
                    root / "staged.json",
                    dict(
                        candidate_id=str(run.candidate_id),
                        ea_sha256=run.ea_sha256,
                        input_sha256=run.input_sha256,
                        terminal_sha256=hashlib.sha256(
                            (runtime / "terminal64.exe").read_bytes()
                        ).hexdigest(),
                        terminal_build=adapter.environment.terminal_build,
                        terminal_build_source="OPERATOR_DECLARED",
                        staged_runtime_files={
                            str(p.relative_to(runtime)): evidence.file_identity(p)
                            for p in sorted(runtime.rglob("*"))
                            if p.is_file()
                        },
                    ),
                )
            if self.cancel_event.is_set():
                raise Blocked(State.CANCELLED)
            run = self.advance(
                run_id, State.RUNNING, terminal_build=adapter.environment.terminal_build
            )
            outcome = adapter.run(run.config, root, runtime, self.cancel_event)
            exit_code = outcome.code
            if outcome.cancelled or self.cancel_event.is_set():
                raise Blocked(State.CANCELLED)
            if outcome.timed_out:
                raise Blocked(State.TIMEOUT)
            log = evidence.logs(runtime)
            (root / "tester-sanitized.log").write_text(log, encoding="utf-8", newline="\n")
            failure = observed_failure(log)
            if failure:
                observed = (
                    "LICENSE_BLOCKED"
                    if failure == State.BLOCKED_LICENSE
                    else (
                        "TESTER_ACCESS_BLOCKED"
                        if failure == State.BLOCKED_TESTER_ACCESS
                        else (
                            "INITIALIZATION_FAILED"
                            if failure == State.INITIALIZATION_FAILED
                            else "UNKNOWN"
                        )
                    )
                )
                raise Blocked(failure)
            if exit_code != 0:
                raise Blocked(State.TESTER_FAILED)
            report_path = runtime / (run_id.hex + ".htm")
            if not report_path.is_file() or report_path.is_symlink():
                raise Blocked(State.REPORT_MISSING)
            try:
                if report_path.stat().st_size > 16 * 1024 * 1024:
                    raise ValueError("REPORT_SIZE_LIMIT")
                raw = report_path.read_bytes()
                text = decode_report(raw)
            except ValueError:
                raise Blocked(State.REPORT_PARSE_FAILED) from None
            if evidence.safe_log(text) != text:
                report_path.write_text(evidence.safe_log(text), encoding="utf-8")
                evidence.write_json(
                    root / "report-rejected.json",
                    dict(
                        raw_sha256=hashlib.sha256(raw).hexdigest(),
                        reason="CREDENTIAL_LIKE_REPORT_CONTENT",
                    ),
                )
                raise Blocked(State.REPORT_PARSE_FAILED)
            (root / "report.htm").write_bytes(raw)
            if not real_ticks_verified(log):
                raise Blocked(State.BLOCKED_REAL_TICKS_UNAVAILABLE)
            run = self.advance(run_id, State.PARSING, exit_code=exit_code)
            try:
                result = parse(raw, run_id, run.config.project_id, run.candidate_id)
                experts = (
                    adapter.report_experts()
                    if isinstance(adapter, InstalledExecutionAdapter)
                    else {run_id.hex}
                )
                if result.metadata["Expert"].removesuffix(".ex5") not in experts:
                    raise ValueError("REPORT_EXPERT_MISMATCH")
                if result.metadata["Currency"] not in {"UNAVAILABLE", run.config.currency}:
                    raise ValueError("REPORT_CURRENCY_MISMATCH")
                if result.metadata["Leverage"] != f"1:{run.config.leverage}":
                    raise ValueError("REPORT_LEVERAGE_MISMATCH")
                if (
                    result.metadata["Symbol"] != run.config.symbol
                    or result.metadata["timeframe"] != run.config.timeframe
                ):
                    raise ValueError("REPORT_BINDING_MISMATCH")
                if (result.metadata["from_date"], result.metadata["to_date"]) != (
                    f"{run.config.from_date:%Y.%m.%d}",
                    f"{run.config.to_date:%Y.%m.%d}",
                ):
                    raise ValueError("REPORT_INTERVAL_MISMATCH")
                if result.metadata["Model"] not in {
                    "UNAVAILABLE",
                    "Every tick based on real ticks",
                }:
                    raise ValueError("REPORT_MODEL_MISMATCH")
                if result.metrics["initial_deposit"] != str(run.config.initial_deposit):
                    from decimal import Decimal

                    if (
                        Decimal(str(result.metrics["initial_deposit"]))
                        != run.config.initial_deposit
                    ):
                        raise ValueError("REPORT_DEPOSIT_MISMATCH")
            except (ValueError, ArithmeticError):
                raise Blocked(State.REPORT_PARSE_FAILED) from None
            # Cancellation and completion share a linearization point: an accepted cancel
            # cannot race a successful commit. Late cancellation reports already terminal.
            with self.guard:
                if self.cancel_event.is_set():
                    raise Blocked(State.CANCELLED)
                evidence.write_json(root / "result.json", result.model_dump(mode="json"))
                if (
                    parse(
                        (root / "report.htm").read_bytes(),
                        run_id,
                        run.config.project_id,
                        run.candidate_id,
                    )
                    != result
                ):
                    raise Blocked(State.REPORT_PARSE_FAILED)
                evidence.write_json(
                    root / "execution.json",
                    dict(
                        status="COMPLETE",
                        exit_code=exit_code,
                        started_at=run.started_at.isoformat() if run.started_at else None,
                        completed_at=datetime.now(UTC).isoformat(),
                    ),
                )
                identity = evidence.finalize(root, "COMPLETE")
                with self.engine.begin() as conn:
                    conn.execute(
                        insert(store.results).values(
                            id=str(run_id), body=result.model_dump(mode="json")
                        )
                    )
                    store.advance(
                        conn,
                        run_id,
                        State.COMPLETE,
                        exit_code=exit_code,
                        result_identity=result.result_identity,
                        evidence_identity=identity,
                        observed_tester_status="SUCCESS",
                        diagnostic="BASELINE_COMPLETE",
                    )
        except Exception as exc:
            status = exc.status if isinstance(exc, Blocked) else State.TESTER_FAILED
            if isinstance(exc, ValueError) and str(exc).startswith("BLOCKED_"):
                try:
                    status = State(str(exc))
                except ValueError:
                    pass
            if self.cancel_event.is_set():
                status = State.CANCELLED
            identity = None
            try:
                if root is not None and root.is_dir() and not (root / "manifest.json").exists():
                    if runtime is not None and not (root / "tester-sanitized.log").exists():
                        try:
                            diagnostic_log = evidence.logs(runtime)
                        except (OSError, ValueError):
                            diagnostic_log = (
                                "DIAGNOSTICS_UNAVAILABLE_OR_SIZE_LIMIT; PRIMARY_OUTCOME_PRESERVED"
                            )
                        (root / "tester-sanitized.log").write_text(diagnostic_log, encoding="utf-8")
                    evidence.write_json(
                        root / "failure.json",
                        dict(
                            status=status.value,
                            exit_code=exit_code,
                            completed_at=datetime.now(UTC).isoformat(),
                        ),
                    )
                    identity = evidence.finalize(root, status.value)
            except (OSError, ValueError):
                pass  # Original evidence retained; DB failure is still explicit, never COMPLETE.
            try:
                self.advance(
                    run_id,
                    status,
                    exit_code=exit_code,
                    evidence_identity=identity,
                    observed_tester_status=observed,
                    diagnostic=status.value,
                )
            except Exception:
                # Interrupted persistence is detected under the OS lock on the next start.
                pass
        finally:
            handle.close()

    def close(self) -> None:
        with self.guard:
            self.cancel_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
