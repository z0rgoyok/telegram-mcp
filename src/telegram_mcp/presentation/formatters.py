from __future__ import annotations

from typing import Any


def format_markdown(tool_name: str, payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        error = payload.get("error") or {}
        code = error.get("code", "PROVIDER_ERROR")
        message = error.get("message", "Unknown error")
        return f"[{tool_name}] {code}: {message}"

    data = payload.get("data")
    if data is None:
        return f"[{tool_name}] ok"

    lines = [f"[{tool_name}] ok"]
    if isinstance(data, dict):
        lines.extend(_render_dict(data, indent=0))
    elif isinstance(data, list):
        lines.extend(_render_list(data, indent=0))
    else:
        lines.append(str(data))

    meta = payload.get("meta") or {}
    cursor = meta.get("cursor")
    has_more = bool(meta.get("has_more"))
    if has_more:
        lines.append("has_more: true")
    if cursor:
        lines.append(f"cursor: {cursor}")
    return "\n".join(lines)


def _render_dict(value: dict[str, Any], *, indent: int) -> list[str]:
    prefix = "  " * indent
    lines: list[str] = []
    for key, item in value.items():
        if isinstance(item, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(_render_dict(item, indent=indent + 1))
        elif isinstance(item, list):
            lines.append(f"{prefix}{key}:")
            lines.extend(_render_list(item, indent=indent + 1))
        else:
            lines.append(f"{prefix}{key}: {item}")
    return lines


def _render_list(items: list[Any], *, indent: int) -> list[str]:
    prefix = "  " * indent
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            lines.append(f"{prefix}-")
            lines.extend(_render_dict(item, indent=indent + 1))
        elif isinstance(item, list):
            lines.append(f"{prefix}-")
            lines.extend(_render_list(item, indent=indent + 1))
        else:
            lines.append(f"{prefix}- {item}")
    if not lines:
        lines.append(f"{prefix}-")
    return lines
