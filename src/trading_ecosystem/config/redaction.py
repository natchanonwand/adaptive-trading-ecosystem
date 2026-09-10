"""Attach this filter to each owned handler before emitting application logs."""

import logging
import re
from collections.abc import Iterable

from pydantic import SecretStr
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[SecretStr] = ()) -> None:
        super().__init__()
        values = [s for s in secrets if s.get_secret_value()]
        # Register the decoded password as well as the complete configured URL,
        # so even an isolated credential fragment is masked.
        for secret in tuple(values):
            try:
                password = make_url(secret.get_secret_value()).password
                if password:
                    values.append(SecretStr(password))
            except (ValueError, SQLAlchemyError):
                pass
        self._secrets = tuple(values)

    def __repr__(self) -> str:
        return "RedactingFilter(secrets=[REDACTED])"

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self._secrets:
            message = message.replace(secret.get_secret_value(), "[REDACTED]")
        message = re.sub(r"\bpostgres(?:ql)?(?:\+\w+)?://[^\s]+", "[REDACTED_URL]", message)
        message = re.sub(
            r"(?i)\b(password|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+",
            r"\1=[REDACTED]",
            message,
        )
        record.msg, record.args = message, ()
        # Arbitrary exception messages may contain credentials, including driver URLs.
        if record.exc_info or record.exc_text:
            record.msg += " [exception details redacted]"
            record.exc_info = None
            record.exc_text = None
        record.stack_info = None
        return True
