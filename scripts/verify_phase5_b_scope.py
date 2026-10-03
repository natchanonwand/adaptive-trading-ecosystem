"""Phase 5B allowlist, frozen tags/bytes, ignored evidence and tester-only scope."""

import ast
import hashlib
import json
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_ecosystem.tester.adapter import configuration_text
from trading_ecosystem.tester.checkpoint import verify_checkpoint
from trading_ecosystem.tester.contracts import Configuration

STOPPED_REPORT_SHA = (
    "386a5dbd4a5fbf061186a842f74f333d7ddea302033d20cd5188e7f1bde8be82"  # pragma: allowlist secret
)
BASE = "e83c41b3d41704c276f98b0912439d13400eb490"  # pragma: allowlist secret
ORIGINAL = "ec87ad23a1bbb805f033af59cf2e9991af755191"  # pragma: allowlist secret
CHECKPOINT = "a76d896ac031c85951b300d6fa946b93f084ab70"  # pragma: allowlist secret
# Phase 5B.0.2 permits only readiness contracts, UX, migration and their checks.
FIX_FILES = {
    "src/trading_ecosystem/workbench/contracts.py",
    "src/trading_ecosystem/workbench/store.py",
    "src/trading_ecosystem/workbench/api.py",
    "src/trading_ecosystem/tester/contracts.py",
    "src/trading_ecosystem/tester/service.py",
    "tests/integration/test_workbench.py",
    "tests/integration/test_baseline.py",
    "dashboard/src/workbench/BaselinePanel.tsx",
    "dashboard/tests/baseline.test.tsx",
    "scripts/verify_phase5_b_scope.py",
    "docs/PHASE5_B_AUTOMATED_BASELINE.md",
    "PHASE5_B_0_1_REPORT.md",
}
FIX_FILES.update(
    {
        "src/trading_ecosystem/tester/readiness.py",
        "src/trading_ecosystem/tester/checkpoint.py",
        "src/trading_ecosystem/tester/store.py",
        "src/trading_ecosystem/tester/api.py",
        "src/trading_ecosystem/tester/adapter.py",
        "migrations/baseline/versions/0002_readiness.py",
        "dashboard/src/workbench/ReadinessPanel.tsx",
        "dashboard/src/workbench/Workbench.tsx",
        "dashboard/src/workbench/api.ts",
        "dashboard/tests/readiness.test.tsx",
        "tests/test_phase5b_readiness.py",
        "tests/integration/test_baseline_readiness.py",
        "PHASE5_B_0_2_REPORT.md",
        "PHASE5_B1_ACCEPTANCE_REPORT.md",
    }
)
FIX_FILES.difference_update(
    {
        "src/trading_ecosystem/workbench/contracts.py",
        "src/trading_ecosystem/workbench/store.py",
        "src/trading_ecosystem/workbench/api.py",
        "tests/integration/test_workbench.py",
        "dashboard/tests/baseline.test.tsx",
        "PHASE5_B_0_1_REPORT.md",
    }
)
FIX_FILES.update(
    {
        "src/trading_ecosystem/tester/environment.py",
        "src/trading_ecosystem/tester/bootstrap.py",
        "tests/test_phase5b_environment.py",
        "PHASE5_B1A_REPORT.md",
    }
)
CHANGED = {
    "src/trading_ecosystem/workbench/__main__.py",
    "dashboard/src/workbench/Workbench.tsx",
    "dashboard/src/workbench/api.ts",
    "src/trading_ecosystem/workbench/contracts.py",
    "src/trading_ecosystem/workbench/store.py",
    "src/trading_ecosystem/workbench/api.py",
    "tests/integration/test_workbench.py",
}
NEW = {
    "alembic-baseline.ini",
    "PHASE5_B_REPORT.md",
    "PHASE5_B_0_1_REPORT.md",
    "docs/PHASE5_B_AUTOMATED_BASELINE.md",
    "scripts/verify_phase5_b.ps1",
    "scripts/verify_phase5_b_scope.py",
    "scripts/verify_phase5_b_evidence.py",
    "scripts/phase5_b_acceptance_readiness.py",
    "dashboard/src/workbench/BaselinePanel.tsx",
    "dashboard/tests/baseline.test.tsx",
    "tests/fixtures/phase5b_report.htm",
    "tests/phase5b_helpers.py",
    "tests/test_phase5b.py",
    "tests/integration/test_baseline.py",
}


NEW.update(FIX_FILES - CHANGED)

# Phase 5B.1B uses the actual frozen calibration checkpoint, preserving every earlier file.
CHECKPOINT = "3ad73e72821026da91254100f065f37a390b015e"  # pragma: allowlist secret
FIX_FILES = {
    "src/trading_ecosystem/tester/environment.py",
    "src/trading_ecosystem/tester/bootstrap.py",
    "src/trading_ecosystem/tester/adapter.py",
    "src/trading_ecosystem/tester/checkpoint.py",
    "scripts/verify_phase5_b_scope.py",
    "tests/test_phase5b_environment.py",
    "tests/test_phase5b.py",
    "dashboard/src/workbench/ReadinessPanel.tsx",
    "dashboard/src/workbench/api.ts",
    "dashboard/tests/readiness.test.tsx",
    "PHASE5_B1B_REPORT.md",
}
NEW.update(FIX_FILES - CHANGED)


CHECKPOINT = "bd5780b59068f6dd81d2bb55cc748dbf978658e8"  # pragma: allowlist secret
FIX_FILES = {
    "src/trading_ecosystem/tester/environment.py",
    "src/trading_ecosystem/tester/bootstrap.py",
    "src/trading_ecosystem/tester/process.py",
    "src/trading_ecosystem/tester/handshake.py",
    "src/trading_ecosystem/tester/checkpoint.py",
    "scripts/verify_phase5_b_scope.py",
    "tests/test_phase5b_handshake.py",
    "dashboard/src/workbench/ReadinessPanel.tsx",
    "dashboard/src/workbench/api.ts",
    "dashboard/tests/readiness.test.tsx",
    "PHASE5_B1C_REPORT.md",
}
NEW.update(FIX_FILES - CHANGED)


CHECKPOINT = "38e022b8dd70d245500ecfa8ea332a99061f1bd2"  # pragma: allowlist secret
FIX_FILES = {
    "src/trading_ecosystem/tester/no_trade.py",
    "src/trading_ecosystem/tester/probe_expert.mq5",
    "src/trading_ecosystem/tester/bootstrap.py",
    "src/trading_ecosystem/tester/environment.py",
    "src/trading_ecosystem/tester/checkpoint.py",
    "scripts/verify_phase5_b_scope.py",
    "tests/test_phase5b_no_trade.py",
    "PHASE5_B1D_REPORT.md",
}
NEW.update(FIX_FILES - CHANGED)


CHECKPOINT = "3f88a030d7f6b67d47f7a3fea01b490a8ca0bde5"  # pragma: allowlist secret
FIX_FILES = {
    "src/trading_ecosystem/tester/research_account.py",
    "src/trading_ecosystem/tester/account_probe.py",
    "src/trading_ecosystem/tester/checkpoint.py",
    "scripts/verify_phase5_b_scope.py",
    "tests/test_phase5b_research_account.py",
    "PHASE5_B1E_REPORT.md",
}
NEW.update(FIX_FILES - CHANGED)


CHECKPOINT = "55071a4f8be825f5aef9d920d3182ef241f2b158"  # pragma: allowlist secret
FIX_FILES = {
    "src/trading_ecosystem/tester/qualification.py",
    "src/trading_ecosystem/tester/checkpoint.py",
    "scripts/verify_phase5_b_scope.py",
    "tests/test_phase5b_qualification.py",
    "tests/integration/test_candidate_qualification.py",
    "PHASE5_B1F_REPORT.md",
}
NEW.update(FIX_FILES - CHANGED)


CHECKPOINT = "6b9567a9ad76f27e63f98aeeae98350bcc1700fd"  # pragma: allowlist secret
FIX_FILES = {
    "src/trading_ecosystem/tester/installed_profile.py",
    "src/trading_ecosystem/tester/qualification.py",
    "src/trading_ecosystem/tester/api.py",
    "src/trading_ecosystem/tester/checkpoint.py",
    "scripts/verify_phase5_b_scope.py",
    "tests/test_phase5b_installed_profile.py",
    "tests/integration/test_candidate_qualification.py",
    "dashboard/src/workbench/CandidateReadiness.tsx",
    "dashboard/src/workbench/ReadinessPanel.tsx",
    "dashboard/tests/candidate-readiness.test.tsx",
    "PHASE5_B1G_REPORT.md",
}
NEW.update(FIX_FILES - CHANGED)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    verify_checkpoint(Path.cwd())
    diagnostic = Path("PHASE5_B1_ACCEPTANCE_REPORT.md")
    if hashlib.sha256(diagnostic.read_bytes()).hexdigest() != STOPPED_REPORT_SHA:
        raise ValueError("STOPPED_ACCEPTANCE_REPORT_CHANGED")
    if git("rev-parse", "phase5a-v0.1.1^{commit}") != BASE:
        raise ValueError("CORRECTIVE_PHASE5A_TAG_CHANGED")
    subprocess.check_call(["git", "merge-base", "--is-ancestor", BASE, CHECKPOINT])
    fixes = set(git("diff", "--name-only", CHECKPOINT).splitlines())
    fixes.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    if fixes - FIX_FILES:
        raise ValueError("UNEXPECTED_READINESS_FIX_CHANGE: " + repr(sorted(fixes - FIX_FILES)))
    if git("rev-parse", "phase5a-v0.1.0^{commit}") != ORIGINAL:
        raise ValueError("ORIGINAL_PHASE5A_TAG_CHANGED")
    changed = set(git("diff", "--name-only", BASE).splitlines())
    unexpected = {
        name
        for name in changed - CHANGED - NEW
        if not name.startswith(("src/trading_ecosystem/tester/", "migrations/baseline/"))
    }
    if unexpected:
        raise ValueError("UNEXPECTED_FROZEN_CHANGE: " + repr(sorted(unexpected)))
    new = git("ls-files", "--others", "--exclude-standard").splitlines()
    for name in new:
        if name not in NEW and not name.startswith(
            ("src/trading_ecosystem/tester/", "migrations/baseline/")
        ):
            raise ValueError("UNEXPECTED_PHASE5B_FILE: " + name)
    snapshot = json.loads(Path(".local/phase5_b/baseline.json").read_text(encoding="utf-8-sig"))
    for name, expected in snapshot.items():
        if (
            name not in CHANGED
            and hashlib.sha256(Path(name).read_bytes()).hexdigest().upper() != expected.upper()
        ):
            raise ValueError("FROZEN_RAW_BYTES_CHANGED: " + name)
    forbidden_imports = {"MetaTrader5", "requests", "urllib.request"}
    forbidden_calls = {"order_send", "order_check", "eval", "exec", "system", "popen"}
    for path in Path("src/trading_ecosystem/tester").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            imports = (
                [n.name for n in node.names]
                if isinstance(node, ast.Import)
                else ([node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            )
            if any(
                n in forbidden_imports or n.startswith("trading_ecosystem.execution")
                for n in imports
            ):
                raise ValueError("BROKER_OR_NETWORK_IMPORT: " + str(path))
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                )
                if name in forbidden_calls:
                    raise ValueError("FORBIDDEN_EXECUTION_CALL: " + str(path))
    cfg = Configuration(
        baseline_run_id=UUID(int=1),
        project_id=UUID(int=2),
        symbol="XAUUSDm",
        timeframe="H1",
        from_date=date(2026, 9, 1),
        to_date=date(2026, 9, 2),
        initial_deposit=Decimal("10000"),
        leverage=100,
    )
    lines = configuration_text(
        cfg, cfg.baseline_run_id.hex, cfg.baseline_run_id.hex + ".htm", "Synthetic-Demo"
    ).splitlines()
    for required in (
        "Optimization=0",
        "Model=4",
        "ForwardMode=0",
        "UseCloud=0",
        "UseRemote=0",
        "AllowLiveTrading=0",
        "AllowDllImport=0",
        "Enabled=0",
        "Expert=",
        "Script=",
        "ReplaceReport=0",
    ):
        if required not in lines:
            raise ValueError("TESTER_CONFIGURATION_SAFETY_CHANGED")
    for name in (
        ".local/phase5_b/runs/probe/report.htm",
        ".local/phase5_b/runs/probe/terminal/MQL5/Experts/probe.ex5",
        ".local/phase5_b/environment.json",
    ):
        git("check-ignore", "--no-index", name)
    if any(p.lower().endswith((".ex5", ".ex4")) for p in git("ls-files").splitlines() + new):
        raise ValueError("EXECUTABLE_EA_IN_GIT_SCOPE")
    print(
        f"PASS: Phase 5B scope; {len(snapshot) - len(CHANGED)} unchanged snapshot files; "
        "both Phase 5A tags; tester-only configuration; ignored evidence"
    )


if __name__ == "__main__":
    main()
