from __future__ import annotations

import base64
import json
from typing import Any

from ..domain.errors import ErrorCode, ToolError


def _encode(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(cursor: str) -> dict[str, Any]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive parsing
        raise ToolError(ErrorCode.VALIDATION_ERROR, "Invalid cursor", {"cursor": cursor}) from exc

    if not isinstance(value, dict):
        raise ToolError(ErrorCode.VALIDATION_ERROR, "Invalid cursor payload", {"cursor": cursor})
    return value


def encode_offset_cursor(offset: int) -> str:
    return _encode({"kind": "offset", "value": offset})


def decode_offset_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    payload = _decode(cursor)
    if payload.get("kind") != "offset" or not isinstance(payload.get("value"), int):
        raise ToolError(ErrorCode.VALIDATION_ERROR, "Cursor kind mismatch", {"cursor": cursor})
    value = int(payload["value"])
    if value < 0:
        raise ToolError(ErrorCode.VALIDATION_ERROR, "Cursor value cannot be negative", {"cursor": cursor})
    return value


def encode_message_cursor(message_id: int) -> str:
    return _encode({"kind": "message_id", "value": message_id})


def decode_message_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return None
    payload = _decode(cursor)
    if payload.get("kind") != "message_id" or not isinstance(payload.get("value"), int):
        raise ToolError(ErrorCode.VALIDATION_ERROR, "Cursor kind mismatch", {"cursor": cursor})
    value = int(payload["value"])
    if value <= 0:
        raise ToolError(ErrorCode.VALIDATION_ERROR, "Cursor message_id must be positive", {"cursor": cursor})
    return value
