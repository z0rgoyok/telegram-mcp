from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from tests.conftest import load_attr, load_module

execute_use_case = load_attr("telegram_mcp.application.executor", "execute_use_case")
TelegramUseCases = load_attr("telegram_mcp.application.use_cases", "TelegramUseCases")
models = load_module("telegram_mcp.domain.models")


class ContractReader:
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
            items=[models.ChatRef(id=1, type=models.ChatType.GROUP, name="A")],
            has_more=False,
            next_offset=None,
        )

    async def list_unread_dialogs(self, *, limit: int = 50, offset: int = 0) -> Any:
        self._touch += 1
        _ = (limit, offset)
        return models.Page(
            items=[models.ChatRef(id=1, type=models.ChatType.GROUP, name="A", unread_count=1)],
            has_more=False,
        )

    async def resolve_chat(self, *, query: str, limit: int = 20) -> list[Any]:
        self._touch += 1
        _ = (query, limit)
        return [models.ChatRef(id=1, type=models.ChatType.GROUP, name="A")]

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
        message = models.MessageInfo(
            id=1,
            date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            sender="bot",
            text="hello",
            chat_id=1,
            chat_name="A",
        )
        return models.Page(items=[message], has_more=False)

    async def get_message_context(
        self,
        *,
        chat_id: int | str,
        message_id: int,
        before: int,
        after: int,
    ) -> Any:
        self._touch += 1
        _ = (chat_id, before, after)
        message = models.MessageInfo(
            id=message_id,
            date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            sender="bot",
            text="hello",
            chat_id=1,
            chat_name="A",
        )
        return models.MessageContext(target=message, before=[], after=[])

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
        message = models.MessageInfo(
            id=root_message_id,
            date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            sender="bot",
            text="hello",
            chat_id=1,
            chat_name="A",
        )
        return models.ThreadMessages(root=message, page=models.Page(items=[], has_more=False))

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
        _ = (query, chat_id, sender_query, limit, offset_id, time_range)
        return await self.get_messages(chat_id=1)

    async def get_chat_snapshot(
        self,
        *,
        chat_id: int | str,
        recent_limit: int,
        include_pinned: bool,
    ) -> Any:
        self._touch += 1
        _ = (chat_id, recent_limit, include_pinned)
        chat = models.ChatInfo(id=1, type=models.ChatType.GROUP, name="A", unread_count=0)
        return models.ChatSnapshot(chat=chat, recent_messages=[], pinned_messages=[])

    async def get_message_media(
        self,
        *,
        chat_id: int | str,
        message_id: int,
    ) -> Any:
        self._touch += 1
        _ = (chat_id, message_id)
        return models.MediaFile(
            chat_id=1,
            message_id=message_id,
            kind=models.MediaKind.PHOTO,
            mime_type="image/jpeg",
            file_name="image.jpg",
            size_bytes=4,
            content_url="http://proxy.local/media/token",
            url_source=models.MediaUrlSource.PROXY,
        )

    async def get_auth_status(self) -> Any:
        self._touch += 1
        return models.AuthStatus(
            connected=True,
            authorized=True,
            user_id=1,
            name="Tester",
            username="tester",
        )

    async def health_check(self) -> Any:
        self._touch += 1
        return models.HealthStatus(status="ok", connected=True, authorized=True)


async def _expect_ok(payload: dict[str, object]) -> None:
    assert payload["ok"] is True
    assert "data" in payload
    assert payload["error"] is None
    assert "meta" in payload


@pytest.mark.asyncio
async def test_json_contract_for_all_tools() -> None:
    use_cases = TelegramUseCases(ContractReader())

    responses = [
        await execute_use_case(use_cases.resolve_chat, query="A"),
        await execute_use_case(use_cases.list_chats),
        await execute_use_case(use_cases.list_unread_chats),
        await execute_use_case(use_cases.get_messages, chat_id=1),
        await execute_use_case(use_cases.get_message_context, chat_id=1, message_id=1),
        await execute_use_case(use_cases.get_thread_messages, chat_id=1, root_message_id=1),
        await execute_use_case(use_cases.search_messages, query="hello"),
        await execute_use_case(use_cases.get_chat_snapshot, chat_id=1),
        await execute_use_case(use_cases.get_message_media, chat_id=1, message_id=1),
        await execute_use_case(use_cases.get_auth_status),
        await execute_use_case(use_cases.health_check),
    ]

    for payload in responses:
        await _expect_ok(payload)
