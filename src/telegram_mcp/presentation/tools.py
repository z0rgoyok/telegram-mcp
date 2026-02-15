from __future__ import annotations

import sys
from datetime import datetime

from ..domain.models import ChatFilter
from ..domain.ports import TelegramReader
from . import formatters


async def list_chats(
    reader: TelegramReader,
    limit: int = 50,
    filter: str = "all",
) -> str:
    """List Telegram chats/channels/groups.

    Args:
        limit: Number of chats to return (max 200).
        filter: Filter by type: "all", "channels", "groups", "users".
    """
    try:
        limit = max(1, min(limit, 200))
        chat_filter = ChatFilter(filter)
        chats = await reader.list_dialogs(limit=limit, filter=chat_filter)
        return formatters.format_chat_list(chats)
    except ValueError:
        return f'Invalid filter "{filter}". Use: all, channels, groups, users.'
    except Exception as exc:
        print(f"list_chats error: {exc}", file=sys.stderr)
        return f"Error listing chats: {exc}"


async def get_messages(
    reader: TelegramReader,
    chat_id: int | str = 0,
    limit: int = 50,
    offset_date: str | None = None,
    search: str | None = None,
) -> str:
    """Get messages from a specific Telegram chat.

    Args:
        chat_id: Chat ID (number) or @username.
        limit: Number of messages to return (max 200).
        offset_date: Only messages before this date (ISO format, e.g. 2025-01-15).
        search: Search text within the chat.
    """
    try:
        limit = max(1, min(limit, 200))
        parsed_date: datetime | None = None
        if offset_date:
            parsed_date = datetime.fromisoformat(offset_date)

        resolved_id: int | str = chat_id
        if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
            resolved_id = int(chat_id)

        messages = await reader.get_messages(
            chat_id=resolved_id,
            limit=limit,
            offset_date=parsed_date,
            search=search,
        )
        return formatters.format_messages(messages)
    except Exception as exc:
        print(f"get_messages error: {exc}", file=sys.stderr)
        return f"Error getting messages: {exc}"


async def search_messages(
    reader: TelegramReader,
    query: str = "",
    chat_id: int | str | None = None,
    limit: int = 20,
) -> str:
    """Search messages globally or within a specific chat.

    Args:
        query: Search query text.
        chat_id: Optional chat ID or @username to search within.
        limit: Number of results (max 100).
    """
    try:
        if not query.strip():
            return "Query cannot be empty."
        limit = max(1, min(limit, 100))

        resolved_id: int | str | None = chat_id
        if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
            resolved_id = int(chat_id)

        messages = await reader.search_global(
            query=query,
            chat_id=resolved_id,
            limit=limit,
        )
        return formatters.format_search_results(messages)
    except Exception as exc:
        print(f"search_messages error: {exc}", file=sys.stderr)
        return f"Error searching messages: {exc}"
