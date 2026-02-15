from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from tests.conftest import load_attr, load_module

decode_message_cursor = load_attr("telegram_mcp.application.cursor", "decode_message_cursor")
execute_use_case = load_attr("telegram_mcp.application.executor", "execute_use_case")
TelegramUseCases = load_attr("telegram_mcp.application.use_cases", "TelegramUseCases")

ErrorCode = load_attr("telegram_mcp.domain.errors", "ErrorCode")
ToolError = load_attr("telegram_mcp.domain.errors", "ToolError")
models = load_module("telegram_mcp.domain.models")


class StubReader:
    def __init__(self) -> None:
        self._touch = 0

    async def list_dialogs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        chat_filter: Any = models.ChatFilter.ALL,
        query: str | None = None,
        unread_only: bool = False,
    ) -> Any:
        self._touch += 1
        _ = (limit, offset, chat_filter, query, unread_only)
        return models.Page(
            items=[
                models.ChatRef(
                    id=1,
                    type=models.ChatType.GROUP,
                    name="Engineering",
                    username="eng",
                    unread_count=3,
                    last_activity=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
                )
            ],
            has_more=False,
            next_offset=None,
        )

    async def list_unread_dialogs(self, *, limit: int = 50, offset: int = 0) -> Any:
        self._touch += 1
        return await self.list_dialogs(limit=limit, offset=offset)

    async def resolve_chat(self, *, query: str, limit: int = 20) -> list[Any]:
        self._touch += 1
        _ = (query, limit)
        return [
            models.ChatRef(
                id=1,
                type=models.ChatType.GROUP,
                name="Engineering",
                username="eng",
                unread_count=3,
                last_activity=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
            )
        ]

    async def get_messages(
        self,
        *,
        chat_id: int | str,
        limit: int = 50,
        offset_id: int | None = None,
        time_range: Any = None,
        order: Any = models.MessageOrder.DESC,
        search: str | None = None,
    ) -> Any:
        self._touch += 1
        _ = (chat_id, limit, offset_id, time_range, order, search)
        return models.Page(
            items=[
                models.MessageInfo(
                    id=101,
                    date=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                    sender="alice",
                    sender_id=42,
                    text="hello",
                    chat_id=1,
                    chat_name="Engineering",
                )
            ],
            has_more=True,
            next_offset=99,
        )

    async def get_message_context(
        self,
        *,
        chat_id: int | str,
        message_id: int,
        before: int,
        after: int,
    ) -> Any:
        self._touch += 1
        _ = (chat_id, message_id, before, after)
        target = models.MessageInfo(
            id=100,
            date=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            sender="alice",
            sender_id=42,
            text="target",
            chat_id=1,
            chat_name="Engineering",
        )
        return models.MessageContext(target=target, before=[], after=[])

    async def get_thread_messages(
        self,
        *,
        chat_id: int | str,
        root_message_id: int,
        limit: int = 50,
        offset_id: int | None = None,
    ) -> Any:
        self._touch += 1
        _ = (chat_id, limit, offset_id)
        root = models.MessageInfo(
            id=root_message_id,
            date=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            sender="alice",
            sender_id=42,
            text="root",
            chat_id=1,
            chat_name="Engineering",
        )
        page = models.Page(items=[], has_more=False, next_offset=None)
        return models.ThreadMessages(root=root, page=page)

    async def search_messages(
        self,
        *,
        query: str,
        chat_id: int | str | None = None,
        sender_query: str | None = None,
        limit: int = 20,
        offset_id: int | None = None,
        time_range: Any = None,
    ) -> Any:
        self._touch += 1
        _ = (query, chat_id, sender_query, offset_id, time_range)
        return await self.get_messages(chat_id=1, limit=limit)

    async def get_chat_snapshot(
        self,
        *,
        chat_id: int | str,
        recent_limit: int,
        include_pinned: bool,
    ) -> Any:
        self._touch += 1
        _ = (chat_id, recent_limit, include_pinned)
        chat = models.ChatInfo(
            id=1,
            type=models.ChatType.GROUP,
            name="Engineering",
            unread_count=3,
            username="eng",
            last_activity=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
        )
        return models.ChatSnapshot(chat=chat, recent_messages=[], pinned_messages=[])

    async def get_auth_status(self) -> Any:
        self._touch += 1
        return models.AuthStatus(
            connected=True,
            authorized=True,
            user_id=1,
            name="Alice",
            username="alice",
        )

    async def health_check(self) -> Any:
        self._touch += 1
        return models.HealthStatus(status="ok", connected=True, authorized=True)


@pytest.mark.asyncio
async def test_search_messages_empty_query_returns_validation_error() -> None:
    use_cases = TelegramUseCases(StubReader())

    response = await execute_use_case(use_cases.search_messages, query="   ")

    assert response["ok"] is False
    assert response["error"]["code"] == ErrorCode.VALIDATION_ERROR.value


@pytest.mark.asyncio
async def test_get_messages_returns_cursor_and_utc_iso_dates() -> None:
    use_cases = TelegramUseCases(StubReader())

    response = await execute_use_case(use_cases.get_messages, chat_id=1)

    assert response["ok"] is True
    assert response["meta"]["has_more"] is True
    assert decode_message_cursor(response["meta"]["cursor"]) == 99
    assert response["data"]["items"][0]["date"].endswith("Z")


@pytest.mark.asyncio
async def test_list_chats_invalid_filter_returns_validation_error() -> None:
    use_cases = TelegramUseCases(StubReader())

    response = await execute_use_case(use_cases.list_chats, chat_filter="bad")

    assert response["ok"] is False
    assert response["error"]["code"] == ErrorCode.VALIDATION_ERROR.value


@pytest.mark.asyncio
async def test_get_messages_invalid_time_range_returns_validation_error() -> None:
    use_cases = TelegramUseCases(StubReader())

    response = await execute_use_case(
        use_cases.get_messages,
        chat_id=1,
        from_date="2026-01-03T00:00:00Z",
        to_date="2026-01-01T00:00:00Z",
    )

    assert response["ok"] is False
    assert response["error"]["code"] == ErrorCode.VALIDATION_ERROR.value


@pytest.mark.asyncio
async def test_execute_use_case_maps_unhandled_exception_to_provider_error() -> None:
    async def broken_handler() -> dict[str, object]:
        raise RuntimeError("boom")

    response = await execute_use_case(broken_handler)

    assert response["ok"] is False
    assert response["error"]["code"] == ErrorCode.PROVIDER_ERROR.value


@pytest.mark.asyncio
async def test_execute_use_case_keeps_domain_errors() -> None:
    async def broken_handler() -> dict[str, object]:
        raise ToolError(ErrorCode.UNAUTHORIZED, "not authorized")

    response = await execute_use_case(broken_handler)

    assert response["ok"] is False
    assert response["error"]["code"] == ErrorCode.UNAUTHORIZED.value
