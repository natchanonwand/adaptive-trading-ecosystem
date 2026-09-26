"""The narrow freeze reconciliation cannot mask content or evidence changes."""

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

import pytest

_spec = importlib.util.spec_from_file_location(
    "phase5a_verifier_under_test",
    Path(__file__).resolve().parents[1] / "scripts" / "verify_phase5_a_scope.py",
)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def verify_reconciled_bytes(
    name: str, expected: str, current: bytes, proof: dict[str, Any], frozen: bytes
) -> None:
    _module.verify_reconciled_bytes(name, expected, current, proof, frozen)


def fixture() -> tuple[str, bytes, dict[str, Any], bytes]:
    old = b"first\r\nsecond\nthird\r\n"
    current = b"first\nsecond\nthird\n"
    expected = hashlib.sha256(old).hexdigest()
    proof = {
        "reason": "LINE_ENDING_NORMALIZATION",
        "pre_freeze_sha256": expected,
        "current_sha256": hashlib.sha256(current).hexdigest(),
        "normalized_sha256": hashlib.sha256(current).hexdigest(),
        "pre_freeze_crlf_line_ranges": [[1, 1], [3, 3]],
    }
    return expected, current, proof, current


def test_exact_mixed_newline_reconstruction() -> None:
    verify_reconciled_bytes("example.md", *fixture())


@pytest.mark.parametrize(
    "replacement",
    [
        b"changed\n",
        b"first \nsecond\nthird\n",
        b"first\nsecond\nthird",
        b"first\r\nsecond\r\nthird\r\n",
    ],
)
def test_unrecorded_bytes_rejected(replacement: bytes) -> None:
    expected, _, proof, frozen = fixture()
    with pytest.raises(ValueError):
        verify_reconciled_bytes("example.md", expected, replacement, proof, frozen)


def test_cannot_forge_reconstruction_or_git_content() -> None:
    expected, current, proof, frozen = fixture()
    with pytest.raises(ValueError):
        verify_reconciled_bytes(
            "example.md", expected, current, {**proof, "pre_freeze_crlf_line_ranges": []}, frozen
        )
    with pytest.raises(ValueError):
        verify_reconciled_bytes("example.md", expected, current, proof, b"different git blob\n")


@pytest.mark.parametrize(
    "name",
    [
        "data/datasets/report.json",
        "research/results.json",
        ".local/evidence.json",
        "reports/new-evidence.json",
    ],
)
def test_evidence_never_uses_text_reconciliation(name: str) -> None:
    with pytest.raises(ValueError, match="FORBIDDEN"):
        verify_reconciled_bytes(name, *fixture())
