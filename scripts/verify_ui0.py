"""Presentation-only UI-0 boundary and immutable research evidence checks."""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = "f6e3621973c55bc479c7be0b9d8833de0436c6f4"  # pragma: allowlist secret
ALLOWED = {
    "dashboard/src/workbench/Workbench.tsx",
    "dashboard/src/workbench/workbench.css",
    "dashboard/src/workbench/retro.tsx",
    "dashboard/tests/retro.test.tsx",
    "docs/UI_RETRO_DESIGN_SYSTEM.md",
    "UI0_REPORT.md",
    "scripts/verify_ui0.py",
    "scripts/verify_ui0.ps1",
}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    for ref in ("HEAD", "origin/main", "phase5c-contract-v0.1.0^{commit}"):
        if git("rev-parse", ref) != BASE:
            raise ValueError("UI0_FROZEN_BASELINE_MISMATCH")
    tags = json.loads(Path(".local/ui0/tags-before.json").read_bytes())
    if git("show-ref", "--tags").splitlines() != tags:
        raise ValueError("FROZEN_TAG_CHANGED")
    changed = set(git("diff", "--name-only", BASE).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    if changed - ALLOWED:
        raise ValueError("NON_PRESENTATION_CHANGE: " + repr(sorted(changed - ALLOWED)))
    for label, path in (
        ("frozen", ".local/phase4_e/preserved-evidence.json"),
        ("historical", ".local/phase5_c0/preserved-before.json"),
    ):
        records = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        for name, sha in records.items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != sha.lower():
                raise ValueError("EVIDENCE_CHANGED: " + name)
        print(f"PASS: {len(records)} {label} evidence files byte-identical")
    git("check-ignore", "--no-index", ".local/ui0/review.png")
    git("diff", "--check")
    print(
        "PASS: UI-0 presentation scope; all backend/API/experiment contracts unchanged; "
        "tags unchanged"
    )


if __name__ == "__main__":
    main()
