"""Installed profile transport for the common Baseline lifecycle; never stages an EX5."""

import hashlib
import json
import os
from pathlib import Path
from threading import Event

from sqlalchemy import Engine

from trading_ecosystem.tester import account_probe, evidence, process, research_account
from trading_ecosystem.tester.adapter import Adapter, Blocked
from trading_ecosystem.tester.contracts import Configuration, Run, State
from trading_ecosystem.tester.environment import TerminalBinding, local_path, validate_binding
from trading_ecosystem.tester.execution_plan import (
    CandidateExecutionPlan,
    load_qualification,
    plan_installed,
    typed,
    verify_account,
)
from trading_ecosystem.tester.handshake import Observer
from trading_ecosystem.tester.parser import decode_report


class InstalledExecutionAdapter(Adapter):
    def __init__(
        self,
        engine: Engine,
        artifacts: Path,
        run: Run,
        binding_path: Path,
        qualification_path: Path,
        proof_root: Path,
    ) -> None:
        self.engine, self.artifacts, self.attempt = engine, artifacts, run
        try:
            self.binding_path = local_path(binding_path.absolute())
            self.qualification_path = local_path(qualification_path.absolute())
            self.proof_root = local_path(proof_root.absolute())
            self.pinned = TerminalBinding.model_validate_json(self.binding_path.read_bytes())
            super().__init__(validate_binding(self.pinned, run.config.symbol))
        except (OSError, ValueError) as error:
            raise typed(error) from None
        self.plan: CandidateExecutionPlan | None = None

    def checked_plan(self, root: Path) -> CandidateExecutionPlan:
        try:
            pinned = TerminalBinding.model_validate_json(self.binding_path.read_bytes())
            if pinned != self.pinned:
                raise Blocked(State.BLOCKED_TERMINAL_IDENTITY_MISMATCH)
            with self.engine.connect() as conn:
                return plan_installed(
                    conn,
                    self.artifacts,
                    self.attempt,
                    load_qualification(self.qualification_path),
                    pinned,
                    self.proof_root,
                    root.resolve(),
                )
        except (ValueError, OSError) as error:
            raise typed(error) from None

    def prepare(
        self,
        config: Configuration,
        ea: bytes,
        expected_hash: str,
        root: Path,
        broker_name: str,
        cancel: Event,
    ) -> Path:
        if ea or config != self.attempt.config or expected_hash != self.attempt.ea_sha256:
            raise Blocked(State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH)
        if broker_name != self.pinned.broker_name:
            raise Blocked(State.BLOCKED_SYMBOL)
        if cancel.is_set():
            raise Blocked(State.CANCELLED)
        if self.plan is not None:
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        self.plan = self.checked_plan(root)
        evidence.write_json(
            root / "execution-plan.json",
            {"identity": self.plan.identity, "content": self.plan.model_dump(mode="json")},
        )
        # Only newly captured output enters the shared parser/evidence pipeline.
        runtime = root / "native-readback"
        runtime.mkdir()
        return runtime

    def run(
        self,
        config: Configuration,
        root: Path,
        runtime: Path,
        cancel: Event,
    ) -> process.Outcome:
        plan = self.plan
        if plan is None or config != self.attempt.config or self.checked_plan(root) != plan:
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        try:
            saved = json.loads((root / "execution-plan.json").read_bytes())
            if saved != {"identity": plan.identity, "content": plan.model_dump(mode="json")}:
                raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
            if (root / "native-launch.json").exists():
                raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        except (ValueError, OSError):
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH) from None
        if runtime.resolve() != (root / "native-readback").resolve():
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        # This is the future-launch boundary. Tests replace discovery/close/process with fakes.
        try:
            context = research_account.discover(self.pinned)
            verify_account(plan, context)
        except (ValueError, OSError) as error:
            raise typed(error) from None
        if cancel.is_set():
            raise Blocked(State.CANCELLED)
        profile = local_path(self.pinned.terminal_data_root)
        logs = {
            "logs": profile / "logs",
            "Tester/terminal": profile / "Tester/logs",
            "Tester/agents": Path(os.environ["APPDATA"]) / "MetaQuotes/Tester" / profile.name,
        }
        before = account_probe.log_positions(logs)
        if list(profile.glob(config.baseline_run_id.hex + "*")):
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        account_probe.restrict_runtime(root)
        account_probe.close_session(context, self.pinned)
        # Rehash after session shutdown and immediately before process creation.
        if self.checked_plan(root) != plan:
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        observer = Observer(self.pinned.terminal_executable.parent)
        ini = local_path(root.resolve() / "native-account.ini")
        launched = False
        outcome: process.Outcome | None = None
        try:
            with account_probe.ephemeral_ini(ini, plan.native_config, context):
                if cancel.is_set():
                    raise Blocked(State.CANCELLED)
                evidence.write_json(
                    root / "native-launch.json",
                    {
                        "plan_identity": plan.identity,
                        "maximum_launches": 1,
                        "execution_strategy": plan.execution_strategy,
                    },
                )
                launched = True
                outcome = process.execute(
                    self.pinned.terminal_executable,
                    ["/config:" + str(ini)],
                    self.pinned.terminal_executable.parent,
                    plan.timeout_seconds,
                    cancel,
                    observer,
                )
                return outcome
        finally:
            observer.close()
            if launched:
                try:
                    account_probe.capture_logs(logs, before, runtime, context.login)
                    report = local_path(Path(plan.report_path))
                    if report.is_file():
                        if report.stat().st_size > 16 * 1024 * 1024:
                            raise Blocked(State.REPORT_PARSE_FAILED)
                        raw = report.read_bytes()
                        text = decode_report(raw)
                        # A native report may contain the account identifier. Preserve its
                        # raw hash, but persist only the existing sanitized evidence policy.
                        safe = evidence.safe_log(
                            text.replace(str(context.login), "[ACCOUNT_REDACTED]")
                        )
                        evidence.write_json(
                            root / "native-report-origin.json",
                            {
                                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                                "account_identifier_redacted": safe != text,
                            },
                        )
                        with (runtime / report.name).open("x", encoding="utf-8") as stream:
                            stream.write(safe)
                except (OSError, ValueError, Blocked):
                    # Timeout/cancellation is the primary native outcome. A truncated
                    # report or log must not replace it with a parsing/storage failure.
                    if outcome is None or not (outcome.timed_out or outcome.cancelled):
                        raise
                    evidence.write_json(
                        root / "diagnostic-capture.json",
                        {
                            "status": "CAPTURE_INCOMPLETE_PRIMARY_OUTCOME_PRESERVED",
                        },
                    )
                finally:
                    account_probe.remove_probe_reports(profile, config.baseline_run_id)
                    evidence.write_json(
                        root / "native-cleanup.json",
                        {
                            "ephemeral_config_removed": not ini.exists(),
                            "candidate_copied": False,
                            "processes": list(observer.processes.values()),
                        },
                    )

    def report_experts(self) -> set[str]:
        if self.plan is None:
            return set()
        reference = self.plan.expert_reference.removesuffix(".ex5")
        return {reference, reference.rsplit("\\", 1)[-1]}
