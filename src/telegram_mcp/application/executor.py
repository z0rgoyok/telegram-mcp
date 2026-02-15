from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ..domain.errors import ToolError
from .responses import error_response, provider_error


async def execute_use_case(
    handler: Callable[..., Awaitable[dict[str, Any]]],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        return await handler(**kwargs)
    except ToolError as exc:
        return error_response(exc)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return error_response(provider_error("Unexpected provider failure", details={"error": str(exc)}))
