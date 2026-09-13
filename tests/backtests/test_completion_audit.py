"""Reject ambiguous partial state without touching final evidence."""

import runpy
from pathlib import Path

import pytest

AUDIT = runpy.run_path("scripts/verify_phase3_3b_evidence.py")


def test_identical_intentional_partial_is_accepted(tmp_path: Path) -> None:
    content = b'{"synthetic":true}'
    (tmp_path / "result.json").write_bytes(content)
    (tmp_path / "result.partial").write_bytes(content)
    AUDIT["verify_partials"](tmp_path, {"result.json"})
    assert (tmp_path / "result.json").read_bytes() == content


@pytest.mark.parametrize("mode", ["orphan", "conflict", "extra_final", "missing_final"])
def test_ambiguous_or_incomplete_evidence_rejected(tmp_path: Path, mode: str) -> None:
    (tmp_path / "result.json").write_bytes(b"{}")
    if mode == "orphan":
        (tmp_path / "unknown.partial").write_bytes(b"{}")
    elif mode == "conflict":
        (tmp_path / "result.partial").write_bytes(b'{"different":true}')
    elif mode == "extra_final":
        (tmp_path / "extra.json").write_bytes(b"{}")
    else:
        (tmp_path / "result.json").unlink()
    with pytest.raises(ValueError):
        AUDIT["verify_partials"](tmp_path, {"result.json"})
