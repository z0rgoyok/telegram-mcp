from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..domain.errors import ErrorCode, ToolError


def new_request_id() -> str:
    return str(uuid4())


def success_response(
    data: Any,
    *,
    cursor: str | None = None,
    has_more: bool = False,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error": None,
        "meta": {
            "cursor": cursor,
            "has_more": has_more,
            "request_id": request_id or new_request_id(),
        },
    }


def error_response(error: ToolError, *, request_id: str | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": error.code.value,
            "message": error.message,
            "details": error.details or {},
        },
        "meta": {
            "cursor": None,
            "has_more": False,
            "request_id": request_id or new_request_id(),
        },
    }


def provider_error(message: str, *, details: dict[str, Any] | None = None) -> ToolError:
    return ToolError(
        code=ErrorCode.PROVIDER_ERROR,
        message=message,
        details=details,
    )
