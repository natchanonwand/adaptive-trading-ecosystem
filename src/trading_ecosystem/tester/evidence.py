"""Append-only run evidence and safe diagnostics; never serve native reports as HTML."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def file_identity(path: Path) -> str:
    """Hash potentially large cached files without loading them into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(value, out, sort_keys=True, indent=2)
        out.write("\n")


def safe_log(value: str) -> str:
    return "".join(
        "[REDACTED CREDENTIAL-LIKE LINE]" + line[len(line.rstrip("\r\n")) :]
        if re.search(r"password|passwd|token|secret|api.?key|license.?key", line, re.I)
        else line
        for line in value.splitlines(keepends=True)
    )


def logs(runtime: Path) -> str:
    chunks = []
    total = 0
    for folder in (runtime / "logs", runtime / "Tester"):
        for path in sorted(folder.rglob("*.log")):
            if path.is_symlink() or not path.resolve().is_relative_to(runtime.resolve()):
                raise ValueError("DIAGNOSTIC_PATH_INVALID")
            total += path.stat().st_size
            if total > 8 * 1024 * 1024:
                raise ValueError("DIAGNOSTIC_SIZE_LIMIT")
            raw = path.read_bytes()
            text = raw.decode(
                "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig",
                errors="replace",
            )
            sanitized = safe_log(text)
            if sanitized != text:
                # Owned, newly generated native diagnostics only; no prior evidence is touched.
                path.write_text(sanitized, encoding="utf-8", newline="\n")
            chunks.append(sanitized)
    return "\n".join(chunks)


def finalize(root: Path, status: str) -> str:
    identities = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.iterdir())
        if p.is_file()
    }
    body = {"status": status, "files": identities}
    identity = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    write_json(root / "manifest.json", {**body, "identity": identity})
    # Independent readback before accepting the manifest identity.
    for name, sha in identities.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:
            raise ValueError("EVIDENCE_READBACK_FAILED")
    return identity
