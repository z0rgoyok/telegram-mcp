from __future__ import annotations

import json
from typing import Any

from ..domain.errors import ErrorCode, ToolError
from ..domain.models import MediaKind, TimeRange
from ..domain.ports import ChatExportWriter, TelegramReader
from .cursor import (
    decode_message_cursor,
    decode_offset_cursor,
    encode_message_cursor,
    encode_offset_cursor,
)
from .responses import success_response
from .serializers import (
    auth_status_to_dict,
    batch_item_to_dict,
    chat_action_result_to_dict,
    chat_activity_summary_to_dict,
    chat_activity_to_dict,
    chat_export_to_dict,
    chat_info_to_dict,
    chat_ref_to_dict,
    context_to_dict,
    dialog_filter_to_dict,
    export_file_to_dict,
    health_to_dict,
    media_file_to_dict,
    mention_chat_activity_to_dict,
    message_to_dict,
    snapshot_to_dict,
    thread_to_dict,
)
from .validators import (
    parse_chat_filter,
    parse_chat_id,
    parse_dialog_filter,
    parse_dialog_folder,
    parse_order,
    parse_time_range,
    require_int_in_range,
    require_text,
)


class TelegramUseCases:
    def __init__(
        self,
        reader: TelegramReader,
        chat_export_writer: ChatExportWriter | None = None,
    ) -> None:
        self._reader = reader
        self._chat_export_writer = chat_export_writer

    @staticmethod
    def _parse_required_from_date_page(
        *,
        limit: int,
        cursor: str | None,
        from_date: str | None,
        to_date: str | None,
    ) -> tuple[int, int, TimeRange]:
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        offset = decode_offset_cursor(cursor)
        time_range = parse_time_range(from_date=from_date, to_date=to_date)
        if time_range is None or time_range.from_date is None:
            raise ToolError(
                ErrorCode.VALIDATION_ERROR,
                "from_date is required",
                {"field": "from_date"},
            )
        return normalized_limit, offset, time_range

    async def resolve_chat(
        self,
        *,
        query: str,
        limit: int = 20,
        dialog_filter: int | str | None = None,
    ) -> dict[str, Any]:
        normalized_query = require_text(query, "query")
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        normalized_dialog_filter = parse_dialog_filter(dialog_filter)

        chats = await self._reader.resolve_chat(
            query=normalized_query,
            limit=normalized_limit,
            dialog_filter=normalized_dialog_filter,
        )
        return success_response(
            {
                "query": normalized_query,
                "dialog_filter": normalized_dialog_filter,
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
        folder: int | None = None,
        dialog_filter: int | str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        normalized_filter = parse_chat_filter(chat_filter)
        normalized_folder = parse_dialog_folder(folder)
        normalized_dialog_filter = parse_dialog_filter(dialog_filter)
        normalized_query = query.strip() if isinstance(query, str) and query.strip() else None
        if normalized_folder is not None and normalized_dialog_filter is not None:
            raise ToolError(
                ErrorCode.VALIDATION_ERROR,
                "folder and dialog_filter cannot be used together",
                {"fields": ["folder", "dialog_filter"]},
            )
        offset = decode_offset_cursor(cursor)

        page = await self._reader.list_dialogs(
            limit=normalized_limit,
            offset=offset,
            chat_filter=normalized_filter,
            query=normalized_query,
            unread_only=bool(unread_only),
            folder=normalized_folder,
            dialog_filter=normalized_dialog_filter,
        )
        next_cursor = encode_offset_cursor(page.next_offset) if page.next_offset is not None else None
        return success_response(
            {
                "items": [chat_ref_to_dict(chat) for chat in page.items],
                "filter": normalized_filter.value,
                "query": normalized_query,
                "unread_only": bool(unread_only),
                "folder": normalized_folder,
                "dialog_filter": normalized_dialog_filter,
                "count": len(page.items),
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def list_unread_chats(
        self,
        *,
        folder: int | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        normalized_folder = parse_dialog_folder(folder)
        offset = decode_offset_cursor(cursor)

        page = await self._reader.list_unread_dialogs(
            limit=normalized_limit,
            offset=offset,
            folder=normalized_folder,
        )
        next_cursor = encode_offset_cursor(page.next_offset) if page.next_offset is not None else None

        return success_response(
            {
                "items": [chat_ref_to_dict(chat) for chat in page.items],
                "folder": normalized_folder,
                "count": len(page.items),
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def list_dialog_filters(self) -> dict[str, Any]:
        filters = await self._reader.list_dialog_filters()
        return success_response(
            {
                "items": [dialog_filter_to_dict(item) for item in filters],
                "count": len(filters),
            }
        )

    async def unsubscribe_from_channel(
        self,
        *,
        chat_id: int | str,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id)
        result = await self._reader.unsubscribe_from_channel(chat_id=normalized_chat_id)
        return success_response(chat_action_result_to_dict(result))

    async def leave_chat(
        self,
        *,
        chat_id: int | str,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id)
        result = await self._reader.leave_chat(chat_id=normalized_chat_id)
        return success_response(chat_action_result_to_dict(result))

    async def list_my_sent_chats(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit, offset, time_range = self._parse_required_from_date_page(
            limit=limit,
            cursor=cursor,
            from_date=from_date,
            to_date=to_date,
        )

        page = await self._reader.list_my_sent_chats(
            limit=normalized_limit,
            offset=offset,
            time_range=time_range,
        )
        next_cursor = encode_offset_cursor(page.next_offset) if page.next_offset is not None else None
        return success_response(
            {
                "items": [chat_activity_to_dict(activity) for activity in page.items],
                "count": len(page.items),
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def list_mentions_to_me_chats(
        self,
        *,
        mention: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        offset = decode_offset_cursor(cursor)
        time_range = parse_time_range(from_date=from_date, to_date=to_date)
        normalized_mention = await self._resolve_mention(mention)

        page = await self._reader.list_mentions_to_me_chats(
            mention=normalized_mention,
            limit=normalized_limit,
            offset=offset,
            time_range=time_range,
        )
        next_cursor = encode_offset_cursor(page.next_offset) if page.next_offset is not None else None
        return success_response(
            {
                "mention": normalized_mention,
                "items": [mention_chat_activity_to_dict(activity) for activity in page.items],
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
        query: str | None = None,
        chat_id: int | str | None = None,
        sender_query: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_query = query.strip() if isinstance(query, str) and query.strip() else None
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

    async def search_mentions_to_me(
        self,
        *,
        mention: str | None = None,
        chat_id: int | str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id) if chat_id is not None else None
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        offset_id = decode_message_cursor(cursor)
        time_range = parse_time_range(from_date=from_date, to_date=to_date)
        normalized_mention = await self._resolve_mention(mention)

        page = await self._reader.search_mentions_to_me(
            mention=normalized_mention,
            chat_id=normalized_chat_id,
            limit=normalized_limit,
            offset_id=offset_id,
            time_range=time_range,
        )

        next_cursor = encode_message_cursor(page.next_offset) if page.next_offset is not None else None
        return success_response(
            {
                "mention": normalized_mention,
                "items": [message_to_dict(message) for message in page.items],
                "count": len(page.items),
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def list_replies_to_me(
        self,
        *,
        chat_id: int | str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id) if chat_id is not None else None
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        offset_id = decode_message_cursor(cursor)
        time_range = parse_time_range(from_date=from_date, to_date=to_date)

        page = await self._reader.list_replies_to_me(
            chat_id=normalized_chat_id,
            limit=normalized_limit,
            offset_id=offset_id,
            time_range=time_range,
        )

        next_cursor = encode_message_cursor(page.next_offset) if page.next_offset is not None else None
        return success_response(
            {
                "items": [message_to_dict(message) for message in page.items],
                "count": len(page.items),
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def get_messages_batch(
        self,
        *,
        chat_ids: list[int | str],
        limit_per_chat: int = 20,
        from_date: str | None = None,
        to_date: str | None = None,
        order: str = "desc",
        search: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(chat_ids, list) or not chat_ids:
            raise ToolError(
                ErrorCode.VALIDATION_ERROR,
                "chat_ids cannot be empty",
                {"field": "chat_ids"},
            )
        normalized_chat_ids = [parse_chat_id(item) for item in chat_ids]
        normalized_limit = require_int_in_range(
            limit_per_chat,
            "limit_per_chat",
            minimum=1,
            maximum=100,
        )
        normalized_order = parse_order(order)
        time_range = parse_time_range(from_date=from_date, to_date=to_date)
        normalized_search = search.strip() if isinstance(search, str) and search.strip() else None

        items = await self._reader.get_messages_batch(
            chat_ids=normalized_chat_ids,
            limit_per_chat=normalized_limit,
            time_range=time_range,
            order=normalized_order,
            search=normalized_search,
        )
        return success_response(
            {
                "items": [batch_item_to_dict(item) for item in items],
                "count": len(items),
            }
        )

    async def list_media_messages(
        self,
        *,
        chat_id: int | str | None = None,
        media_kind: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id) if chat_id is not None else None
        normalized_limit = require_int_in_range(limit, "limit", minimum=1, maximum=100)
        normalized_media_kind = _parse_media_kind(media_kind)
        offset_id = decode_message_cursor(cursor)
        time_range = parse_time_range(from_date=from_date, to_date=to_date)

        page = await self._reader.list_media_messages(
            chat_id=normalized_chat_id,
            media_kind=normalized_media_kind,
            limit=normalized_limit,
            offset_id=offset_id,
            time_range=time_range,
        )
        next_cursor = encode_message_cursor(page.next_offset) if page.next_offset is not None else None
        return success_response(
            {
                "media_kind": normalized_media_kind.value if normalized_media_kind else None,
                "items": [message_to_dict(message) for message in page.items],
                "count": len(page.items),
            },
            cursor=next_cursor,
            has_more=page.has_more,
        )

    async def list_chat_activity_summary(
        self,
        *,
        mention: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit, offset, time_range = self._parse_required_from_date_page(
            limit=limit,
            cursor=cursor,
            from_date=from_date,
            to_date=to_date,
        )
        normalized_mention = await self._resolve_mention(mention)

        page = await self._reader.list_chat_activity_summary(
            mention=normalized_mention,
            limit=normalized_limit,
            offset=offset,
            time_range=time_range,
        )
        next_cursor = encode_offset_cursor(page.next_offset) if page.next_offset is not None else None
        return success_response(
            {
                "mention": normalized_mention,
                "items": [chat_activity_summary_to_dict(item) for item in page.items],
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

    async def get_message_media(
        self,
        *,
        chat_id: int | str,
        message_id: int,
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id)
        normalized_message_id = require_int_in_range(message_id, "message_id", minimum=1)

        media_file = await self._reader.get_message_media(
            chat_id=normalized_chat_id,
            message_id=normalized_message_id,
        )
        return success_response(media_file_to_dict(media_file))

    async def export_chat(
        self,
        *,
        chat_id: int | str,
        from_date: str | None = None,
        to_date: str | None = None,
        include_media: bool = True,
        order: str = "asc",
    ) -> dict[str, Any]:
        normalized_chat_id = parse_chat_id(chat_id)
        time_range = parse_time_range(from_date=from_date, to_date=to_date)
        normalized_order = parse_order(order)

        chat_export = await self._reader.export_chat(
            chat_id=normalized_chat_id,
            time_range=time_range,
            include_media=bool(include_media),
            order=normalized_order,
        )

        if self._chat_export_writer is None:
            raise ToolError(
                ErrorCode.PROVIDER_ERROR,
                "chat export writer is not configured",
            )

        export_payload = chat_export_to_dict(chat_export)
        export_payload["include_media"] = bool(include_media)
        export_payload["order"] = normalized_order.value
        export_content = json.dumps(export_payload, ensure_ascii=False, indent=2).encode("utf-8")
        export_file = await self._chat_export_writer.write_export_file(
            chat_id=chat_export.chat.id,
            chat_name=chat_export.chat.name,
            content=export_content,
        )

        payload = export_file_to_dict(export_file)
        payload["chat"] = chat_info_to_dict(chat_export.chat)
        payload["count"] = len(chat_export.messages)
        payload["include_media"] = bool(include_media)
        payload["order"] = normalized_order.value
        return success_response(payload)

    async def get_auth_status(self) -> dict[str, Any]:
        status = await self._reader.get_auth_status()
        return success_response(auth_status_to_dict(status))

    async def health_check(self) -> dict[str, Any]:
        status = await self._reader.health_check()
        return success_response(health_to_dict(status))

    async def _resolve_mention(self, mention: str | None) -> str:
        normalized_mention = _normalize_mention(mention)
        if normalized_mention is not None:
            return normalized_mention

        auth_status = await self._reader.get_auth_status()
        if auth_status.username is None:
            raise ToolError(
                ErrorCode.VALIDATION_ERROR,
                "mention is required when Telegram username is not set",
                {"field": "mention"},
            )
        fallback_mention = _normalize_mention(auth_status.username)
        if fallback_mention is None:
            raise ToolError(
                ErrorCode.VALIDATION_ERROR,
                "mention is required when Telegram username is not set",
                {"field": "mention"},
            )
        return fallback_mention


def _normalize_mention(mention: str | None) -> str | None:
    if not isinstance(mention, str) or not mention.strip():
        return None

    trimmed = mention.strip()
    username = trimmed[1:] if trimmed.startswith("@") else trimmed
    if not username:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            "mention cannot be empty",
            {"field": "mention"},
        )
    return f"@{username}"


def _parse_media_kind(value: str | None) -> MediaKind | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    try:
        return MediaKind(normalized)
    except ValueError as exc:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            "Invalid media_kind",
            {"field": "media_kind", "allowed": [item.value for item in MediaKind], "value": value},
        ) from exc
