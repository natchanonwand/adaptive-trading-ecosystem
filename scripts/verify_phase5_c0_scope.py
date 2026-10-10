"""Phase 5C.0 strict change boundary and frozen Phase 5B evidence preservation."""

import ast
import json
import subprocess
from pathlib import Path

from trading_ecosystem.tester.evidence import file_identity

BASE = "d400bda2329a750da1b2a56bca9e8d5350f5f130"  # pragma: allowlist secret
TAG_OBJECT = "d9ab5c931825e159f1440a5915645b27ad795216"  # pragma: allowlist secret
ALLOWED = {
    "src/trading_ecosystem/experiments/__init__.py",
    "src/trading_ecosystem/experiments/contracts.py",
    "src/trading_ecosystem/experiments/governance.py",
    "src/trading_ecosystem/experiments/store.py",
    "src/trading_ecosystem/experiments/api.py",
    "src/trading_ecosystem/workbench/__main__.py",
    "migrations/baseline/versions/0004_experiment_definitions.py",
    "tests/test_experiments.py",
    "tests/integration/test_experiments.py",
    "tests/integration/test_baseline.py",
    "dashboard/src/workbench/ExperimentsPanel.tsx",
    "dashboard/src/workbench/Workbench.tsx",
    "dashboard/tests/experiments.test.tsx",
    "dashboard/tests/workbench.test.tsx",
    "scripts/verify_phase5_c0.ps1",
    "scripts/verify_phase5_c0_scope.py",
    "scripts/verify_phase5_c0_evidence.py",
    "docs/PHASE5_C0_EXPERIMENT_CONTRACT.md",
    "PHASE5_C0_REPORT.md",
}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    if (
        git("rev-parse", "phase5b-tooling-v0.1.13^{commit}") != BASE
        or git("rev-parse", "phase5b-tooling-v0.1.13") != TAG_OBJECT
    ):
        raise ValueError("FROZEN_PHASE5B_TAG_CHANGED")
    for ref in ("HEAD", "origin/main"):
        git("merge-base", "--is-ancestor", BASE, ref)
    old = json.loads(Path(".local/phase5_c0/tags-before.json").read_bytes())
    if git("show-ref", "--tags").splitlines() != old:
        raise ValueError("PRIOR_TAGS_CHANGED")
    changed = set(git("diff", "--name-only", BASE).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    if changed - ALLOWED:
        raise ValueError("OUT_OF_SCOPE_CHANGES: " + repr(sorted(changed - ALLOWED)))
    name = "tests/integration/test_baseline.py"
    original = subprocess.check_output(["git", "show", BASE + ":" + name]).decode()
    if Path(name).read_text() != original.replace(
        '== "0003_reconciled_results"', '== "0004_experiment_definitions"'
    ):
        raise ValueError("FROZEN_TEST_ASSERTIONS_CHANGED")
    for snapshot in (
        ".local/phase5_c0/preserved-before.json",
        ".local/phase4_e/preserved-evidence.json",
    ):
        records = json.loads(Path(snapshot).read_text(encoding="utf-8-sig"))
        for name, sha in records.items():
            if file_identity(Path(name)).lower() != sha.lower():
                raise ValueError("FROZEN_EVIDENCE_CHANGED: " + name)
    for path in Path("src/trading_ecosystem/experiments").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [x.name for x in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(
                n.startswith(
                    (
                        "MetaTrader5",
                        "subprocess",
                        "ctypes",
                        "trading_ecosystem.execution",
                        "trading_ecosystem.mt5",
                    )
                )
                for n in names
            ):
                raise ValueError("NATIVE_EXECUTION_IMPORT")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr
                in {"start", "execute_native", "order_send", "order_check", "Popen"}
            ):
                raise ValueError("NATIVE_EXECUTION_CALL")
    for name in git("ls-files").splitlines():
        if name.lower().endswith((".ex5", ".ex4")) or (
            name.startswith(".local/") or (name.startswith(".env") and name != ".env.example")
        ):
            raise ValueError("PROTECTED_RUNTIME_TRACKED")
    git("check-ignore", "--no-index", ".local/phase5_c0/probe.json")
    print(
        "PASS: Phase 5C.0 scope and lineage; 1044 frozen / 1621 historical files; "
        "no native experiment execution"
    )


if __name__ == "__main__":
    main()
