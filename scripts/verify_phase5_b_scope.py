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
from trading_ecosystem.tester.contracts import Configuration

BASE = "e83c41b3d41704c276f98b0912439d13400eb490"  # pragma: allowlist secret
ORIGINAL = "ec87ad23a1bbb805f033af59cf2e9991af755191"  # pragma: allowlist secret
CHANGED = {
    "src/trading_ecosystem/workbench/__main__.py",
    "dashboard/src/workbench/Workbench.tsx",
    "dashboard/src/workbench/api.ts",
}
NEW = {
    "alembic-baseline.ini",
    "PHASE5_B_REPORT.md",
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


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    for ref in ("HEAD", "phase5a-v0.1.1^{commit}", "origin/main"):
        if git("rev-parse", ref) != BASE:
            raise ValueError("FROZEN_CHECKPOINT_CHANGED: " + ref)
    if git("rev-parse", "phase5a-v0.1.0^{commit}") != ORIGINAL:
        raise ValueError("ORIGINAL_PHASE5A_TAG_CHANGED")
    changed = set(git("diff", "--name-only", BASE).splitlines())
    if changed - CHANGED:
        raise ValueError("UNEXPECTED_FROZEN_CHANGE: " + repr(sorted(changed - CHANGED)))
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
