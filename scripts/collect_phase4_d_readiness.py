"""Collect source-linked release metadata without writing a public README."""

import hashlib
import json
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())
    dashboard = json.loads(Path("dashboard/package.json").read_bytes())
    reports = {}
    for path in sorted(Path().glob("PHASE*_REPORT.md")):
        reports[path.name] = dict(
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            status_excerpt=path.read_text(encoding="utf-8").splitlines()[:10],
        )
    counts = {}
    for name in ("phase4_d.xml", "phase3_6-frontend.xml"):
        root = ET.parse(Path("test-results") / name).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        counts[name] = {
            k: sum(int(s.get(k, "0")) for s in suites)
            for k in ("tests", "failures", "errors", "skipped")
        }
    body = dict(
        reports=reports,
        test_evidence=counts,
        architecture_sources=[
            "docs/PHASE4_D_BEHAVIORAL_RESEARCH_ENGINE.md",
            "docs/PHASE4_C_BEHAVIORAL_FEATURE_ENGINE.md",
        ],
        safety_boundary_source="docs/PHASE4_D_BEHAVIORAL_RESEARCH_ENGINE.md#boundaries-and-limitations",
        dependencies=project["project"]["dependencies"],
        python=project["project"]["requires-python"],
        frontend_dependencies=dashboard["dependencies"],
        asset_evidence_source="PHASE2B_REPORT.md",
        startup_source="docs/PHASE4_D_BEHAVIORAL_RESEARCH_ENGINE.md#offline-commands",
        screenshots=[
            str(p).replace("\\", "/")
            for p in sorted(Path("test-results").glob("phase4_d-research-*.png"))
        ],
        roadmap_source="PHASE4_D_REPORT.md",
        public_readme_created=False,
    )
    Path(".local/phase4_d/readiness.json").write_text(
        json.dumps(body, indent=2) + "\n", encoding="utf-8"
    )
    print("PASS: source-linked readiness metadata collected; no public README generated")


if __name__ == "__main__":
    main()
