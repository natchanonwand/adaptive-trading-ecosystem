import hashlib
import json
from pathlib import Path

from trading_ecosystem.observer.export import verify_export


def main() -> None:
    root = Path(".local/phase4_b/final")
    result = json.loads((root / "qualification.json").read_text())
    if result["provenance"] != "DETERMINISTIC_FAKE_NOT_REAL_EXTERNAL_EA":
        raise ValueError("UNEXPECTED_QUALIFICATION_PROVENANCE")
    for name, expected in result["exports"].items():
        if name not in {"normal-export", "normal-repeat-export", "stress-export"}:
            raise ValueError("INVALID_EXPORT_NAME")
        path = root / name
        if hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest() != expected:
            raise ValueError("OBSERVER_MANIFEST_HASH_MISMATCH")
        verify_export(path)
    print("PASS: Phase 4B immutable fake exports, hashes, replay and no-future context")
    print("REAL_EXTERNAL_EA_SMOKE: BLOCKED / NOT PROVIDED")


if __name__ == "__main__":
    main()
