"""Canonical v1: tagged JSON, sorted map keys, exact Decimal text, UTC times.

Tags avoid collisions between Decimal, string, UUID and timestamp values.
Objects are stored as immutable canonical text, never mutable payload references.
"""

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import field_validator

from trading_ecosystem.domain.primitives import FrozenModel, finite_decimal, utc_timestamp

CANONICAL_VERSION = "tagged-json-v1"
MAX_PAYLOAD_BYTES = 1_000_000


def _decimal_text(value: Decimal) -> str:
    finite_decimal(value)
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _node(value: object, depth: int = 0) -> object:
    if depth > 64:
        raise ValueError("payload nesting limit exceeded")
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, Decimal):
        return ["decimal", _decimal_text(value)]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, UUID):
        return ["uuid", str(value)]
    if isinstance(value, datetime):
        return [
            "utc",
            utc_timestamp(value).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        ]
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("payload keys must be strings")
        return ["map", [[key, _node(value[key], depth + 1)] for key in sorted(value)]]
    if isinstance(value, (list, tuple)):
        return ["list", [_node(item, depth + 1) for item in value]]
    raise ValueError("unsupported payload type; floats and secret wrappers forbidden")


def _decode(node: object, depth: int = 0) -> object:
    if depth > 64 or not isinstance(node, list) or not node:
        raise ValueError("invalid canonical node")
    if node == ["null"]:
        return None
    if len(node) != 2:
        raise ValueError("invalid canonical node")
    tag, value = node
    if tag == "bool" and isinstance(value, bool):
        return value
    if tag in {"str", "int", "decimal", "uuid", "utc"} and isinstance(value, str):
        match tag:
            case "str":
                return value
            case "int":
                return int(value)
            case "decimal":
                return finite_decimal(value)
            case "uuid":
                return UUID(value)
            case "utc":
                return utc_timestamp(value)
    if tag == "list" and isinstance(value, list):
        return [_decode(item, depth + 1) for item in value]
    if tag == "map" and isinstance(value, list):
        result: dict[str, object] = {}
        for pair in value:
            if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
                raise ValueError("invalid canonical map")
            key, item = pair
            if key in result:
                raise ValueError("duplicate canonical map key")
            result[key] = _decode(item, depth + 1)
        return result
    raise ValueError("invalid canonical node")


def canonical_bytes(value: object) -> bytes:
    result = json.dumps(_node(value), ensure_ascii=True, separators=(",", ":")).encode("ascii")
    if len(result) > MAX_PAYLOAD_BYTES:
        raise ValueError("canonical size limit exceeded")
    return result


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class CanonicalPayload(FrozenModel):
    canonical_json: str

    @field_validator("canonical_json")
    @classmethod
    def validate_canonical(cls, value: str) -> str:
        if len(value) > MAX_PAYLOAD_BYTES:
            raise ValueError("canonical size limit exceeded")
        try:
            decoded = _decode(json.loads(value))
            if not isinstance(decoded, dict) or canonical_bytes(decoded).decode("ascii") != value:
                raise ValueError
        except (ValueError, TypeError, RecursionError):
            raise ValueError("invalid canonical payload") from None
        return value

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "CanonicalPayload":
        return cls(canonical_json=canonical_bytes(payload).decode("ascii"))

    @property
    def payload_hash(self) -> str:
        return digest(self.canonical_json.encode("ascii"))
