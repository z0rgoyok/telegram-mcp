from __future__ import annotations

from typing import Any

from ..domain.ports import TelegramReader
from .cursor import (
    decode_message_cursor,
    decode_offset_cursor,
    encode_message_cursor,
    encode_offset_cursor,
)
from .responses import success_response
from .serializers import (
    auth_status_to_dict,
    chat_ref_to_dict,
    context_to_dict,
    health_to_dict,
    message_to_dict,
    snapshot_to_dict,
    thread_to_dict,
)
from .validators import (
    parse_chat_filter,
    parse_chat_id,
    parse_order,
    parse_time_range,
    require_int_in_range,
    require_text,
)


class TelegramUseCases:
    def __init__(self, reader: TelegramReader) -> None:
        self._reader = reader

    async def resolve_chat(self, *, query: str, limit: int = 20) -> dict[str, Any]:
        normalized_query = require_text(query, "query")
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)

        chats = await self._reader.resolve_chat(query=normalized_query, limit=normalized_limit)
        return success_response(
            {
                "query": normalized_query,
                "items": [chat_ref_to_dict(chat) for chat in chats],
                "count": len(chats),
            }
        )

    async def list_chats(
        self,
        *,
        chat_filter: str = "all",
        query: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        normalized_filter = parse_chat_filter(chat_filter)
        normalized_query = query.strip() if isinstance(query, str) and query.strip() else None
        offset = decode_offset_cursor(cursor)

        page = await self._reader.list_dialogs(
            limit=normalized_limit,
            offset=offset,
            chat_filter=normalized_filter,
            query=normalized_query,
            unread_only=bool(unread_only),
        )
        next_cursor = encode_offset_cursor(page.next_offset) if page.next_offset is not None else None
        return success_response(
            {
                "items": [chat_ref_to_dict(chat) for chat in page.items],
                "filter": normalized_filter.value,
                "query": normalized_query,
                "unread_only": bool(unread_only),
                "count": len(page.items),
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def list_unread_chats(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        offset = decode_offset_cursor(cursor)

        page = await self._reader.list_unread_dialogs(limit=normalized_limit, offset=offset)
        next_cursor = encode_offset_cursor(page.next_offset) if page.next_offset is not None else None

        return success_response(
            {
                "items": [chat_ref_to_dict(chat) for chat in page.items],
                "count": len(page.items),
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def get_messages(
        self,
        *,
        chat_id: int | str,
        limit: int = 50,
        cursor: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        order: str = "desc",
        search: str | None = None,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id)
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        normalized_order = parse_order(order)
        offset_id = decode_message_cursor(cursor)
        time_range = parse_time_range(from_date=from_date, to_date=to_date)
        normalized_search = search.strip() if isinstance(search, str) and search.strip() else None

        page = await self._reader.get_messages(
            chat_id=normalized_chat_id,
            limit=normalized_limit,
            offset_id=offset_id,
            time_range=time_range,
            order=normalized_order,
            search=normalized_search,
        )

        next_cursor = encode_message_cursor(page.next_offset) if page.next_offset is not None else None
        return success_response(
            {
                "chat_id": normalized_chat_id,
                "items": [message_to_dict(message) for message in page.items],
                "count": len(page.items),
                "order": normalized_order.value,
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def get_message_context(
        self,
        *,
        chat_id: int | str,
        message_id: int,
        before: int = 20,
        after: int = 20,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id)
        normalized_message_id = require_int_in_range(message_id, "message_id", minimum=1)
        normalized_before = require_int_in_range(before, "before", minimum=0, maximum=50)
        normalized_after = require_int_in_range(after, "after", minimum=0, maximum=50)

        context = await self._reader.get_message_context(
            chat_id=normalized_chat_id,
            message_id=normalized_message_id,
            before=normalized_before,
            after=normalized_after,
        )

        return success_response(context_to_dict(context))

    async def get_thread_messages(
        self,
        *,
        chat_id: int | str,
        root_message_id: int,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id)
        normalized_root_message_id = require_int_in_range(root_message_id, "root_message_id", minimum=1)
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        offset_id = decode_message_cursor(cursor)

        thread = await self._reader.get_thread_messages(
            chat_id=normalized_chat_id,
            root_message_id=normalized_root_message_id,
            limit=normalized_limit,
            offset_id=offset_id,
        )

        next_cursor = (
            encode_message_cursor(thread.page.next_offset)
            if thread.page.next_offset is not None
            else None
        )
        return success_response(
            thread_to_dict(thread),
            cursor=next_cursor,
            has_more=thread.page.has_more,
        )

    async def search_messages(
        self,
        *,
        query: str,
        chat_id: int | str | None = None,
        sender_query: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_query = require_text(query, "query")
        normalized_chat_id = parse_chat_id(chat_id) if chat_id is not None else None
        normalized_sender_query = (
            sender_query.strip()
            if isinstance(sender_query, str) and sender_query.strip()
            else None
        )
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        offset_id = decode_message_cursor(cursor)
        time_range = parse_time_range(from_date=from_date, to_date=to_date)

        page = await self._reader.search_messages(
            query=normalized_query,
            chat_id=normalized_chat_id,
            sender_query=normalized_sender_query,
            limit=normalized_limit,
            offset_id=offset_id,
            time_range=time_range,
        )

        next_cursor = encode_message_cursor(page.next_offset) if page.next_offset is not None else None

        return success_response(
            {
                "query": normalized_query,
                "items": [message_to_dict(message) for message in page.items],
                "count": len(page.items),
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def get_chat_snapshot(
        self,
        *,
        chat_id: int | str,
        recent_limit: int = 20,
        include_pinned: bool = True,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id)
        normalized_recent_limit = require_int_in_range(
            recent_limit,
            "recent_limit",
            minimum=1,
            maximum=50,
        )

        snapshot = await self._reader.get_chat_snapshot(
            chat_id=normalized_chat_id,
            recent_limit=normalized_recent_limit,
            include_pinned=bool(include_pinned),
        )

        return success_response(snapshot_to_dict(snapshot))

    async def get_auth_status(self) -> dict[str, Any]:
        status = await self._reader.get_auth_status()
        return success_response(auth_status_to_dict(status))

    async def health_check(self) -> dict[str, Any]:
        status = await self._reader.health_check()
        return success_response(health_to_dict(status))
