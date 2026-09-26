"""Read-only preservation and campaign evidence verification; never acquire observations."""

import hashlib
import json
from pathlib import Path

from trading_ecosystem.campaigns.finalize import validate
from trading_ecosystem.campaigns.health import audit_read_only


def main() -> None:
    baseline = json.loads(
        Path(".local/phase4_e/preserved-evidence.json").read_text(encoding="utf-8-sig")
    )
    expected = {"historical": 874, "phase4b": 53, "phase4c": 57, "phase4d": 60}
    prefixes = {
        "historical": ("data/datasets/", "data/research/"),
        "phase4b": (".local/phase4_b/",),
        "phase4c": (".local/phase4_c/",),
        "phase4d": (".local/phase4_d/",),
    }
    counts = {key: sum(p.startswith(value) for p in baseline) for key, value in prefixes.items()}
    if counts != expected or len(baseline) != 1044:
        raise ValueError("PHASE4_E_PRESERVATION_BASELINE_SCOPE_MISMATCH")
    for name, sha in baseline.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != sha:
            raise ValueError("PRESERVED_EVIDENCE_CHANGED: " + name)
    if not audit_read_only():
        raise ValueError("READ_ONLY_AUDIT_FAILED")
    campaigns = Path(".local/phase4_e/campaigns")
    frozen = 0
    for path in sorted(campaigns.glob("*")):
        if not path.is_dir():
            raise ValueError("UNEXPECTED_CAMPAIGN_NAMESPACE_FILE")
        if not (path / "manifest.json").exists():
            print(f"CAMPAIGN NOT QUALIFIED: {path.name}; interrupted/running evidence retained")
            continue
        validate(path)
        frozen += 1
    print(f"PASS: {len(baseline)} preserved files unchanged: {counts}")
    print(f"Verified frozen real campaigns: {frozen}; zero does not establish real qualification")


if __name__ == "__main__":
    main()
