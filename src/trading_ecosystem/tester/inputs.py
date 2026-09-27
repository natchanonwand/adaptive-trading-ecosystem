"""Validate opaque visible tester inputs without inventing or optimizing parameters."""

import re


def validate_set(value: str) -> None:
    if not value.strip() or "\x00" in value:
        raise ValueError("INVALID_SET_FILE")
    if re.search(r"password|passwd|token|secret|api.?key|license.?key", value, re.I):
        raise ValueError("CREDENTIAL_INPUT_NOT_ACCEPTED")
    for line in value.splitlines():
        if not line.strip() or line.startswith(";"):
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}=[^\r\n]*", line):
            raise ValueError("INVALID_SET_FILE")
        key, _, raw = line.partition("=")
        if re.search(r"password|passwd|token|secret|api.?key|license.?key", key, re.I):
            raise ValueError("CREDENTIAL_INPUT_NOT_ACCEPTED")
        if "||" in raw:
            # MT5 exports value||start||step||stop||Y/N. Search is never enabled.
            parts = raw.split("||")
            if len(parts) != 5 or parts[-1] != "N":
                raise ValueError("OPTIMIZATION_INPUT_NOT_ACCEPTED")
