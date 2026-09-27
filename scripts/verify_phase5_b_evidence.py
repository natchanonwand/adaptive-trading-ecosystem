"""Read-only independent reload of finalized Phase 5B evidence; partial runs never pass."""

import hashlib
import json
from pathlib import Path

from trading_ecosystem.tester.contracts import Result, Run
from trading_ecosystem.tester.parser import parse


def verify(root: Path) -> str:
    body = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    identity = body.pop("identity")
    expected = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if identity != expected:
        raise ValueError("MANIFEST_IDENTITY_MISMATCH")
    for name, sha in body["files"].items():
        path = root / name
        if (
            Path(name).name != name
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != sha
        ):
            raise ValueError("RUN_EVIDENCE_MISMATCH")
    if body["status"] == "COMPLETE":
        run = Run.model_validate_json((root / "configuration.json").read_bytes())
        normalized = Result.model_validate_json((root / "result.json").read_bytes())
        if (
            parse(
                (root / "report.htm").read_bytes(),
                run.config.baseline_run_id,
                run.config.project_id,
                run.candidate_id,
            )
            != normalized
        ):
            raise ValueError("RESULT_READBACK_MISMATCH")
    return str(identity)


def main() -> None:
    roots = sorted(Path(".local/phase5_b/runs").glob("*/*"))
    complete = 0
    for root in roots:
        if not (root / "manifest.json").is_file():
            raise ValueError("INCOMPLETE_RUN_EVIDENCE: " + root.name)
        verify(root)
        complete += 1
    print(
        f"PASS: {complete} finalized Phase 5B run manifests independently verified "
        "(zero is not real acceptance)"
    )


if __name__ == "__main__":
    main()
