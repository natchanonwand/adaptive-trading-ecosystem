"""Single isolated environment probe; no campaign or result persistence APIs."""

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

from trading_ecosystem.tester.adapter import Adapter
from trading_ecosystem.tester.contracts import Configuration
from trading_ecosystem.tester.environment import TerminalBinding, local_path, validate_binding
from trading_ecosystem.tester.evidence import finalize, write_json
from trading_ecosystem.tester.handshake import Observer, journal
from trading_ecosystem.tester.process import Outcome, execute
from trading_ecosystem.tester.research_account import discover

SOURCE = (  # pragma: allowlist secret
    "4800f441238fd5a0eaff63e7839865770e4af8fcec4f293b6cc40f07a2dcc46f"  # pragma: allowlist secret
)
ARTIFACT = (  # pragma: allowlist secret
    "36e7a042cb8c67eb25ade8a9ce1ce37f0314844842c4ae87e0d84003bb0921a1"  # pragma: allowlist secret
)
CANDIDATE = "b847df2f-2f5b-4941-881a-efaab99300eb"
INPUTS = "InpFastEmaPeriod=20\nInpSlowEmaPeriod=100\n"


def sha(path: Path) -> str:
    return hashlib.sha256(local_path(path).read_bytes()).hexdigest()


def validate_inputs(config: Configuration) -> None:
    if (
        config.symbol != "XAUUSDm"
        or config.timeframe != "M5"
        or config.tester_model != "EVERY_TICK_BASED_ON_REAL_TICKS"
        or config.set_text != INPUTS
        or config.from_date != date(2026, 1, 5)
        or config.to_date != date(2026, 1, 6)
        or config.timeout_seconds != 60
    ):
        raise ValueError("BLOCKED_QUALIFICATION_CONFIG")


def validate_artifact(source: Path, artifact: Path) -> None:
    if sha(source) != SOURCE:
        raise ValueError("BLOCKED_REFERENCE_ARTIFACT_DEFECT")
    if sha(artifact) != ARTIFACT:
        raise ValueError("BLOCKED_ARTIFACT_IDENTITY_MISMATCH")


def assess(text: str, timed_out: bool) -> dict[str, Any]:
    """No success inferred from mere process survival or configured Model=4."""
    lower = text.lower()
    account_denial = any(
        token in lower
        for token in ("no account", "tester not started because the account is not specified")
    )
    status = "ACCOUNT_CONTEXT_FAILURE" if account_denial else "UNKNOWN_INITIALIZATION_FAILURE"
    if "initialization failed" in lower or "oninit failed" in lower:
        status = "EXPERT_ONINIT_FAILURE"
    return {
        "status": status,
        "environment_state": "UNQUALIFIED",
        "timed_out": timed_out,
        "requested_model": "EVERY_TICK_BASED_ON_REAL_TICKS",
        "native_model_observed": "generating based on real ticks" in lower,
        "full_interval_real_tick_coverage": "UNKNOWN",
        "expert_oninit": "FAILED" if status == "EXPERT_ONINIT_FAILURE" else "UNVERIFIED",
        "bootstrap_ready": False,
        "campaign_authorization": "NOT_AUTHORIZED",
        "start_eligible": False,
    }


def run(root: Path, artifact: Path) -> dict[str, Any]:
    """Consume at most one probe; a pre-existing directory prevents any retry."""
    root = local_path(root)
    source = Path(__file__).parent.parent / "experiments/ReferenceEmaCrossM5.mq5"
    validate_artifact(source.resolve(), artifact)
    pinned = TerminalBinding.model_validate_json(
        Path(".local/phase5_b/terminal-binding.json").read_bytes()
    )
    environment = validate_binding(pinned)
    context = discover(pinned)
    prior = json.loads(Path(".local/phase5_b1e/probe/account-binding.json").read_bytes())
    fingerprint = hashlib.sha256(
        UUID(prior["account_binding_id"]).bytes + str(context.login).encode()
    ).hexdigest()
    if fingerprint != prior["account_fingerprint"]:
        raise ValueError("BLOCKED_TESTER_ACCOUNT_BINDING_MISMATCH")
    probe_id = uuid4()
    config = Configuration(
        baseline_run_id=probe_id,
        project_id=UUID("782bd6a2-4f97-5ca4-906a-cbc1dfe5ce2b"),
        symbol="XAUUSDm",
        timeframe="M5",
        from_date=date(2026, 1, 5),
        to_date=date(2026, 1, 6),
        initial_deposit=Decimal("300"),
        leverage=100,
        timeout_seconds=60,
        input_provenance="USER_CONFIRMED_VALUES",
        input_reference="PROJECT_SOURCE: environment qualification only",
        set_text=INPUTS,
    )
    validate_inputs(config)
    root.mkdir(exist_ok=False)
    write_json(
        root / "intent.json",
        {
            "kind": "ENVIRONMENT_QUALIFICATION",
            "probe_id": str(probe_id),
            "candidate_id": CANDIDATE,
            "artifact_sha256": ARTIFACT,
            "source_sha256": SOURCE,
            "account_fingerprint": fingerprint,
            "terminal_binding": pinned.model_dump(mode="json"),
            "configuration": config.model_dump(mode="json"),
            "max_launches": 1,
            "campaign_budget_consumption": 0,
            "performance_evidence": False,
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    adapter = Adapter(environment)
    runtime = adapter.prepare(config, artifact.read_bytes(), ARTIFACT, root, "Exness", Event())
    staged = runtime / "MQL5/Experts" / f"{probe_id.hex}.ex5"
    if sha(staged) != ARTIFACT:
        raise ValueError("BLOCKED_ARTIFACT_IDENTITY_MISMATCH")
    # No authentication database or account material is copied to this empty portable profile.
    # The installed DEMO context is a prerequisite, never proof that this profile authenticated.
    write_json(root / "launch-intent.json", {"probe_id": str(probe_id), "launches": 1})
    observer = Observer(runtime)

    def observed(exe: Path, args: list[str], cwd: Path, timeout: float, cancel: Event) -> Outcome:
        return execute(exe, args, cwd, timeout, cancel, observer)

    adapter.process = observed
    try:
        outcome = adapter.run(config, root, runtime, Event())
        write_json(root / "processes.json", list(observer.processes.values()))
    finally:
        observer.close()
    records = journal(runtime)
    write_json(root / "journal.json", records)
    text = json.dumps(records)
    result = assess(text, outcome.timed_out)
    result.update(
        probe_id=str(probe_id),
        kind="ENVIRONMENT_QUALIFICATION",
        staging="PORTABLE_STAGING_VERIFIED",
        staged_sha256=sha(staged),
        native_exit_code=outcome.code,
        finished_at=datetime.now(UTC).isoformat(),
    )
    write_json(root / "assessment.json", result)
    result["evidence_identity"] = finalize(root, str(result["status"]))
    return result
