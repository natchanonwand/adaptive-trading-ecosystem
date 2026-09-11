"""Scan tracked + nonignored untracked files without printing detected values."""

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    names = (
        subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .split("\0")
    )
    files = sorted({name for name in names if name and Path(name).is_file()})
    blocked = [
        name
        for name in files
        if (Path(name).name.startswith(".env") and Path(name).name != ".env.example")
        or Path(name).suffix in {".key", ".pem", ".p12", ".pfx", ".dump", ".db"}
        or name.startswith((".local/", "secrets/", "data/discovery/", "data/datasets/"))
    ]
    # The package's CLI is used as a subprocess to avoid importing unstable internals.
    command = [
        str(
            Path(sys.executable).with_name(
                "detect-secrets.exe" if sys.platform == "win32" else "detect-secrets"
            )
        ),
        "scan",
        "--all-files",
        "--force-use-all-plugins",
        "--exclude-lines",
        r"^\s*(content-hash|integrity)\s*=",
        *files,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        print("FAIL: secret scanner could not complete (details suppressed)")
        return 1
    findings = json.loads(completed.stdout).get("results", {})
    if blocked or findings:
        for name in blocked:
            print(f"FAIL: forbidden sensitive file tracked: {name}")
        for name, items in findings.items():
            for item in items:
                print(f"FAIL: {name}:{item['line_number']} ({item['type']}; value suppressed)")
        return 1
    print(f"PASS: detect-secrets scanned {len(files)} project files; no findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
