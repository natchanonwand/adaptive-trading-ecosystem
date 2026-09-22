"""Explicit numeric, UTC, scoped identity and privacy boundaries."""

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from trading_ecosystem.domain.arithmetic import arithmetic_context
from trading_ecosystem.domain.canonical import canonical_bytes, digest
from trading_ecosystem.domain.primitives import finite_decimal
from trading_ecosystem.mt5.client import Record


def number(value: object) -> Decimal:
    if isinstance(value, float):
        return finite_decimal(str(value))
    return finite_decimal(value)


def timestamp(seconds: object, milliseconds: object = None) -> datetime:
    has_milliseconds = milliseconds is not None and milliseconds != 0
    raw = milliseconds if has_milliseconds else seconds
    amount = number(raw)
    with arithmetic_context():
        return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
            microseconds=int(amount * (1000 if has_milliseconds else 1000000))
        )


def identity(*parts: object) -> UUID:
    return UUID(hex=digest(canonical_bytes(parts))[:32])


def account_identity(account: Record) -> UUID:
    if not account.get("server") or type(account.get("login")) is not int:
        raise ValueError("ACCOUNT_IDENTITY_REQUIRED")
    return identity("MT5", account.get("company"), account["server"], account["login"])


def normalize(record: Record) -> Record:
    result: Record = {}
    for key, value in record.items():
        if key in {"login", "password", "path", "data_path", "commondata_path"}:
            continue
        if isinstance(value, float):
            result[key] = str(number(value))
        elif key == "comment" and isinstance(value, str):
            result[key] = (
                "[REDACTED]"
                if re.search(r"password|token|secret|credential", value, re.I)
                else value[:2000]
            )
        elif value is None or isinstance(value, (str, int, bool)):
            result[key] = value
        else:
            raise ValueError("UNSUPPORTED_NATIVE_VALUE")
    return result


def history_key(row: Record) -> tuple[int, int, int]:
    return (
        int(row["time"]),
        int(row.get("time_msc") or int(row["time"]) * 1000),
        int(row["ticket"]),
    )
