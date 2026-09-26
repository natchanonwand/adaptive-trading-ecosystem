"""Read-only frozen baseline, artifact ignore and Workbench execution-boundary audit."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

# Public frozen Git commit identity, not a credential.
FROZEN_COMMIT = "ec87ad23a1bbb805f033af59cf2e9991af755191"  # pragma: allowlist secret


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def verify_reconciled_bytes(
    name: str, expected: str, current: bytes, proof: dict[str, Any], frozen: bytes
) -> None:
    """Accept only an explicitly pinned checkout with an exact old-byte reconstruction."""
    if name.startswith(("data/", "research/", ".local/")) or (
        name.startswith("reports/")
        and name not in {"reports/feature_registry.json", "reports/mt5_broker_economics.json"}
    ):
        raise ValueError("EVIDENCE_RECONCILIATION_FORBIDDEN: " + name)
    normalized = current.replace(b"\r\n", b"\n")
    normalized.decode("utf-8", errors="strict")
    ranges = proof["pre_freeze_crlf_line_ranges"]
    reconstructed = b"".join(
        line.replace(b"\n", b"\r\n") if any(a <= i <= z for a, z in ranges) else line
        for i, line in enumerate(normalized.splitlines(keepends=True), 1)
    )
    if (
        proof["reason"] != "LINE_ENDING_NORMALIZATION"
        or proof["pre_freeze_sha256"] != expected.lower()
        or hashlib.sha256(current).hexdigest() != proof["current_sha256"]
        or hashlib.sha256(normalized).hexdigest() != proof["normalized_sha256"]
        or hashlib.sha256(reconstructed).hexdigest() != expected.lower()
        or normalized != frozen
    ):
        raise ValueError("RECONCILIATION_PROOF_FAILED: " + name)


def main() -> None:
    baseline = Path(".local/phase5_a/baseline.json")
    if baseline.exists():
        snapshot = baseline.read_bytes()
        recorded = json.loads(snapshot.decode("utf-8-sig"))
        reconciliation = Path(".local/phase5_a/freeze-reconciliation/manifest.json")
        proofs: dict[str, Any] = {}
        if reconciliation.exists():
            manifest = json.loads(reconciliation.read_text(encoding="utf-8"))
            if (
                manifest["schema_version"] != 1
                or manifest["snapshot_sha256"] != hashlib.sha256(snapshot).hexdigest()
                or manifest["frozen_commit"] != FROZEN_COMMIT
                or git("rev-parse", "phase5a-v0.1.0^{commit}") != manifest["frozen_commit"]
                or git("rev-parse", "phase5a-v0.1.0") != manifest["frozen_tag_object"]
            ):
                raise ValueError("RECONCILIATION_BASELINE_INVALID")
            proofs = manifest["files"]
        for name, sha in recorded.items():
            if name != "dashboard/vite.config.ts":
                current = Path(name).read_bytes()
                actual = hashlib.sha256(current).hexdigest()
                if actual.upper() != sha.upper():
                    if name not in proofs:
                        raise ValueError("FROZEN_FILE_CHANGED: " + name)
                    frozen_blob = subprocess.check_output(["git", "show", "phase5a-v0.1.0:" + name])
                    prior = subprocess.check_output(["git", "show", "2b4a736:" + name])
                    if frozen_blob != prior:
                        raise ValueError("FROZEN_CONTENT_CHANGED: " + name)
                    verify_reconciled_bytes(name, sha, current, proofs[name], frozen_blob)
        print(
            f"PASS: {len(recorded) - 1} prior files verified (exact bytes or explicit "
            "newline proof); Vite multipage entry reviewed"
        )
    # A Git anchor also works on a clean checkout without local snapshot material.
    frozen = git("ls-tree", "-r", "--name-only", "2b4a736").splitlines()
    changed = git("diff", "--name-only", "2b4a736", "--", *frozen).splitlines()
    if set(changed) - {"dashboard/vite.config.ts"}:
        raise ValueError("FROZEN_GIT_BASELINE_CHANGED")
    forbidden_imports = {"MetaTrader5", "subprocess", "ctypes", "requests", "urllib.request"}
    forbidden_calls = {"eval", "exec", "compile", "order_send", "order_check", "system", "popen"}
    for path in Path("src/trading_ecosystem/workbench").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any(
                n in forbidden_imports
                or n.startswith(
                    (
                        "trading_ecosystem.mt5",
                        "trading_ecosystem.discovery",
                        "trading_ecosystem.execution",
                        "trading_ecosystem.backtests",
                    )
                )
                for n in names
            ):
                raise ValueError("EXECUTION_IMPORT: " + str(path))
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                )
                if name in forbidden_calls:
                    raise ValueError("EXECUTION_CALL: " + str(path))
    for extension in ("ex5", "pdf"):
        git("check-ignore", "--no-index", ".local/artifacts/research_projects/probe." + extension)
    if any(p.lower().endswith((".ex5", ".ex4")) for p in git("ls-files").splitlines()):
        raise ValueError("BINARY_TRACKED")
    print("PASS: opaque uploads ignored; no tracked EA binary; Workbench scope audit")


if __name__ == "__main__":
    main()
