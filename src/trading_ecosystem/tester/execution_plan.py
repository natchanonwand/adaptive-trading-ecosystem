"""Immutable, revalidated installed-candidate launch plans; no discovery heuristics."""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Connection

from trading_ecosystem.domain.primitives import FrozenModel
from trading_ecosystem.tester import readiness
from trading_ecosystem.tester.adapter import Blocked
from trading_ecosystem.tester.contracts import Run, State
from trading_ecosystem.tester.environment import TerminalBinding, local_path, validate_binding
from trading_ecosystem.tester.installed_profile import InstalledProfileAdapter, strategy
from trading_ecosystem.tester.qualification import digest, ingestion, qualify, render
from trading_ecosystem.tester.research_account import AccountContext, ResearchAccountBinding


class CandidateExecutionPlan(FrozenModel):
    baseline_run_id: UUID
    candidate_id: UUID
    project_id: UUID
    configuration_id: UUID
    configuration_identity: str
    qualification_identity: str
    execution_strategy: Literal["INSTALLED_PROFILE_REFERENCE"] = "INSTALLED_PROFILE_REFERENCE"
    artifact_sha256: str
    expert_reference: str
    # JSON strings, rather than mutable nested dictionaries, make the plan deeply immutable.
    terminal_binding_json: str
    account_binding_json: str
    native_config: str
    native_config_sha256: str
    report_path: str
    evidence_root: str
    timeout_seconds: int
    lifecycle: Literal["OWNED_PROCESS_TREE_FIXED_TIMEOUT_NO_RETRY_REQUIRED"] = (
        "OWNED_PROCESS_TREE_FIXED_TIMEOUT_NO_RETRY_REQUIRED"
    )

    @property
    def identity(self) -> str:
        return digest(self.model_dump(mode="json"))


def selected_strategy(conn: Connection, run: Run) -> str:
    events = readiness.history(conn, run.config.project_id)
    if (
        not events
        or events[-1]["event_id"] != str(run.authorization_event_id)
        or events[-1]["candidate_id"] != str(run.candidate_id)
        or events[-1]["confirmed"] is not True
    ):
        raise Blocked(State.BLOCKED_AUTHORIZATION_PROVENANCE)
    try:
        return strategy(ingestion(events[-1]["provenance"]))
    except ValueError:
        raise Blocked(State.BLOCKED_CANDIDATE_INGESTION_MODEL) from None


def typed(error: ValueError | OSError) -> Blocked:
    try:
        status = State(str(error))
    except ValueError:
        status = State.BLOCKED_CANDIDATE_PROFILE_MISMATCH
    return Blocked(status)


def plan_installed(
    conn: Connection,
    artifacts: Path,
    run: Run,
    persisted: dict[str, Any],
    pinned: TerminalBinding,
    proof_root: Path,
    output: Path,
) -> CandidateExecutionPlan:
    """Pure DB/file validation; never creates a run, mutates proof, or touches the SDK."""
    try:
        if selected_strategy(conn, run) != "INSTALLED_PROFILE_REFERENCE":
            raise Blocked(State.BLOCKED_CANDIDATE_INGESTION_MODEL)
        record = persisted["execution_binding"]
        bound = record["content"]
        if record["identity"] != digest(bound):
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        if (
            bound["candidate"]["candidate_id"] != str(run.candidate_id)
            or bound["project"]["project_id"] != str(run.config.project_id)
            or bound["project"]["candidate_id"] != str(run.candidate_id)
        ):
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        if (
            bound["artifact"]["artifact_id"] != str(run.artifact_id)
            or bound["artifact"]["sha256"] != run.ea_sha256
        ):
            raise Blocked(State.BLOCKED_ARTIFACT_IDENTITY_MISMATCH)
        if bound["authorization"]["event_id"] != str(run.authorization_event_id):
            raise Blocked(State.BLOCKED_AUTHORIZATION_PROVENANCE)
        if bound["environment"]["terminal_binding"] != pinned.model_dump(mode="json"):
            raise Blocked(State.BLOCKED_TERMINAL_IDENTITY_MISMATCH)
        if bound["environment"]["account_binding"]["environment_classification"] != "DEMO":
            raise Blocked(State.BLOCKED_TESTER_ACCOUNT_NOT_DEMO)
        if run.config.configuration_id is None:
            raise Blocked(State.BASELINE_CONFIGURATION_IDENTITY_MISMATCH)
        current_config = readiness.get_configuration(conn, run.config.configuration_id)
        if current_config != bound["baseline_configuration"]:
            raise Blocked(State.BASELINE_CONFIGURATION_IDENTITY_MISMATCH)
        spec = readiness.BaselineConfiguration.model_validate(current_config["specification"])
        if spec.execution(run.config.baseline_run_id) != run.config:
            raise Blocked(State.BASELINE_CONFIGURATION_IDENTITY_MISMATCH)
        validate_binding(pinned, run.config.symbol)
        # Reuse the saved qualification namespace and exact identities. No filename search.
        current = qualify(
            conn,
            artifacts,
            run.config.project_id,
            run.candidate_id,
            run.config.configuration_id,
            pinned,
            proof_root,
            local_path(Path(bound["evidence_root"])),
            UUID(bound["qualification_id"]),
            installed_profile=True,
        )
        if current["status"] != "CANDIDATE_EXECUTION_READY":
            raise typed(ValueError(current["status"]))
        if current["execution_binding"] != record:
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        InstalledProfileAdapter().dry_run(bound, pinned, proof_root)
        native = render(run.config, bound["expert_reference"], pinned.server)
        report = local_path(pinned.terminal_data_root / (run.config.baseline_run_id.hex + ".htm"))
        output = local_path(output)
        if report.exists():
            raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH)
        return CandidateExecutionPlan(
            baseline_run_id=run.config.baseline_run_id,
            candidate_id=run.candidate_id,
            project_id=run.config.project_id,
            configuration_id=run.config.configuration_id,
            configuration_identity=current_config["configuration_identity"],
            qualification_identity=record["identity"],
            artifact_sha256=run.ea_sha256,
            expert_reference=bound["expert_reference"],
            terminal_binding_json=pinned.model_dump_json(),
            account_binding_json=ResearchAccountBinding.model_validate(
                bound["environment"]["account_binding"]
            ).model_dump_json(),
            native_config=native,
            native_config_sha256=hashlib.sha256(native.encode()).hexdigest(),
            report_path=str(report),
            evidence_root=str(output),
            timeout_seconds=run.config.timeout_seconds,
        )
    except (KeyError, TypeError):
        raise Blocked(State.BLOCKED_CANDIDATE_PROFILE_MISMATCH) from None
    except (ValueError, OSError) as error:
        raise typed(error) from None


def verify_account(plan: CandidateExecutionPlan, current: AccountContext) -> None:
    """Compare a fresh observation to the original salted binding without saving login."""
    expected = ResearchAccountBinding.model_validate_json(plan.account_binding_json)
    actual = current.binding
    if actual.environment_classification != "DEMO":
        raise Blocked(State.BLOCKED_TESTER_ACCOUNT_NOT_DEMO)
    if actual.terminal_binding_id != expected.terminal_binding_id:
        raise Blocked(State.BLOCKED_TERMINAL_IDENTITY_MISMATCH)
    if (actual.server, actual.company) != (expected.server, expected.company):
        raise Blocked(State.BLOCKED_TESTER_ACCOUNT_SERVER_MISMATCH)
    fingerprint = hashlib.sha256(expected.account_binding_id.bytes + str(current.login).encode())
    if fingerprint.hexdigest() != expected.account_fingerprint:
        raise Blocked(State.BLOCKED_TESTER_ACCOUNT_UNBOUND)


def load_qualification(path: Path) -> dict[str, Any]:
    try:
        value: dict[str, Any] = json.loads(local_path(path).read_bytes())
        return value
    except (ValueError, OSError):
        raise Blocked(State.BLOCKED_CANDIDATE_INGESTION_MODEL) from None
