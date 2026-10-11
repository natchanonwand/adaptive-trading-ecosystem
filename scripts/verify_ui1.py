"""Presentation-only UI-1 boundary and immutable research evidence checks."""

import hashlib
import json
import subprocess
from pathlib import Path

BASE = "d75ce607d3c4e5b98aad9d24c4d4127ca76af20c"  # pragma: allowlist secret
ALLOWED = {
    "dashboard/src/workbench/Workbench.tsx",
    "dashboard/src/workbench/BaselinePanel.tsx",
    "dashboard/src/workbench/ResearchSurfaces.tsx",
    "dashboard/src/workbench/workbench.css",
    "dashboard/tests/baseline.test.tsx",
    "dashboard/tests/research-surfaces.test.tsx",
    "docs/UI1_RESEARCH_SURFACES.md",
    "UI1_REPORT.md",
    "scripts/verify_ui1.py",
    "scripts/verify_ui1.ps1",
}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    for ref in ("HEAD", "origin/main", "ui-retro-v0.1.0^{commit}"):
        if git("rev-parse", ref) != BASE:
            raise ValueError("UI1_FROZEN_BASELINE_MISMATCH")
    tags = json.loads(Path(".local/ui1/tags-before.json").read_text(encoding="utf-8-sig"))
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
    git("check-ignore", "--no-index", ".local/ui1/review.png")
    git("diff", "--check")
    print(
        "PASS: UI-1 presentation scope; all backend/API/experiment contracts unchanged; "
        "tags unchanged"
    )


if __name__ == "__main__":
    main()
