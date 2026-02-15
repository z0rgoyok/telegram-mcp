from __future__ import annotations

from datetime import datetime, timezone

from ..domain.errors import ErrorCode, ToolError
from ..domain.models import ChatFilter, MessageOrder, TimeRange


def require_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            f"{name} cannot be empty",
            {"field": name},
        )
    return value.strip()


def require_int_in_range(
    value: int,
    name: str,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if not isinstance(value, int):
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            f"{name} must be an integer",
            {"field": name},
        )
    if value < minimum:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            f"{name} must be >= {minimum}",
            {"field": name, "minimum": minimum},
        )
    if maximum is not None and value > maximum:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            f"{name} must be <= {maximum}",
            {"field": name, "maximum": maximum},
        )
    return value


def parse_chat_filter(value: str) -> ChatFilter:
    try:
        return ChatFilter(value)
    except ValueError as exc:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            "Invalid filter",
            {"allowed": [item.value for item in ChatFilter], "value": value},
        ) from exc


def parse_order(value: str) -> MessageOrder:
    try:
        return MessageOrder(value)
    except ValueError as exc:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            "Invalid order",
            {"allowed": [item.value for item in MessageOrder], "value": value},
        ) from exc


def parse_chat_id(value: int | str | None) -> int | str:
    if value is None:
        raise ToolError(ErrorCode.VALIDATION_ERROR, "chat_id is required", {"field": "chat_id"})
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ToolError(
                ErrorCode.VALIDATION_ERROR,
                "chat_id cannot be empty",
                {"field": "chat_id"},
            )
        if stripped.lstrip("-").isdigit():
            return int(stripped)
        return stripped
    raise ToolError(
        ErrorCode.VALIDATION_ERROR,
        "chat_id must be int or str",
        {"field": "chat_id"},
    )


def parse_iso_datetime(value: str, field_name: str) -> datetime:
    normalized = value.strip()
    if "T" not in normalized:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            f"{field_name} must be ISO8601 datetime with time",
            {"field": field_name, "value": value},
        )
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            f"{field_name} must be ISO8601 datetime",
            {"field": field_name, "value": value},
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_time_range(from_date: str | None, to_date: str | None) -> TimeRange | None:
    parsed_from = parse_iso_datetime(from_date, "from_date") if from_date else None
    parsed_to = parse_iso_datetime(to_date, "to_date") if to_date else None
    if parsed_from is None and parsed_to is None:
        return None
    try:
        return TimeRange(from_date=parsed_from, to_date=parsed_to)
    except ValueError as exc:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            str(exc),
            {"from_date": from_date, "to_date": to_date},
        ) from exc
