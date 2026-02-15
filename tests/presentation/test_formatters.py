from __future__ import annotations

from tests.conftest import load_attr

format_markdown = load_attr("telegram_mcp.presentation.formatters", "format_markdown")


def test_format_markdown_success_payload() -> None:
    payload = {
        "ok": True,
        "data": {"items": [{"id": 1, "name": "Chat"}]},
        "error": None,
        "meta": {"cursor": "abc", "has_more": True, "request_id": "r1"},
    }

    result = format_markdown("list_chats", payload)

    assert "[list_chats] ok" in result
    assert "has_more: true" in result
    assert "cursor: abc" in result


def test_format_markdown_error_payload() -> None:
    payload = {
        "ok": False,
        "data": None,
        "error": {"code": "VALIDATION_ERROR", "message": "bad input", "details": {}},
        "meta": {"cursor": None, "has_more": False, "request_id": "r1"},
    }

    result = format_markdown("search_messages", payload)

    assert "VALIDATION_ERROR" in result
    assert "bad input" in result
