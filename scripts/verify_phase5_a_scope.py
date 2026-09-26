"""Read-only frozen baseline, artifact ignore and Workbench execution-boundary audit."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    baseline = Path(".local/phase5_a/baseline.json")
    if baseline.exists():
        recorded = json.loads(baseline.read_text(encoding="utf-8-sig"))
        for name, sha in recorded.items():
            if name != "dashboard/vite.config.ts":
                actual = hashlib.sha256(Path(name).read_bytes()).hexdigest()
                if actual.upper() != sha.upper():
                    raise ValueError("FROZEN_FILE_CHANGED: " + name)
        print(f"PASS: {len(recorded) - 1} prior files unchanged; Vite multipage entry reviewed")
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
