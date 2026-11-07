"""Bounded JSON input for transports carrying untrusted oversight evidence."""
import json
from typing import Any


def _fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def validate_value(value: Any, depth: int = 0) -> None:
    if depth > 32:
        raise ValueError("excessive nesting")
    if isinstance(value, dict):
        for child in value.values():
            validate_value(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            validate_value(child, depth + 1)
    elif isinstance(value, float) or (type(value) is int and abs(value) > 2**53 - 1):
        raise ValueError("use safe integers or explicit decimal strings")


def parse_bundle(data: bytes) -> dict[str, Any]:
    if len(data) > 262144:
        raise ValueError("oversized bundle")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_fields)
        validate_value(value)
    except RecursionError as exc:
        raise ValueError("excessive nesting") from exc
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value
