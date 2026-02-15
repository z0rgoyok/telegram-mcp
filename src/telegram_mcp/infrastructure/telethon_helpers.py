from __future__ import annotations

from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import cast

from telethon.tl.types import Channel, Chat, User

from ..domain.models import ChatFilter, ChatRef, ChatType, MessageInfo, to_utc


def entity_to_chat_type(entity: object) -> ChatType:
    if isinstance(entity, Channel):
        return ChatType.CHANNEL if getattr(entity, "broadcast", False) else ChatType.GROUP
    if isinstance(entity, Chat):
        return ChatType.GROUP
    return ChatType.USER


def matches_filter(chat_type: ChatType, chat_filter: ChatFilter) -> bool:
    if chat_filter is ChatFilter.ALL:
        return True
    return chat_filter.value == chat_type.value + "s"


def entity_name(entity: object) -> str:
    if isinstance(entity, User) or hasattr(entity, "first_name") or hasattr(entity, "last_name"):
        parts = [
            getattr(entity, "first_name", "") or "",
            getattr(entity, "last_name", "") or "",
        ]
        joined = " ".join(part for part in parts if part).strip()
        if joined:
            return joined
        return str(getattr(entity, "id", "unknown"))
    return (
        getattr(entity, "title", "")
        or getattr(entity, "name", "")
        or str(getattr(entity, "id", "unknown"))
    )


def chat_matches_query(*, query: str, chat_id: int, name: str, username: str | None) -> bool:
    if not query:
        return True

    normalized_name = name.casefold()
    normalized_username = (username or "").casefold()
    query_value = query.casefold().lstrip("@")

    return (
        query_value in normalized_name
        or query_value in normalized_username
        or query_value in str(chat_id)
    )


def chat_rank(chat: ChatRef, query: str) -> tuple[int, str, int]:
    normalized_name = chat.name.casefold()
    normalized_username = (chat.username or "").casefold()

    if normalized_username == query:
        rank = 0
    elif normalized_name == query:
        rank = 1
    elif normalized_username.startswith(query):
        rank = 2
    elif normalized_name.startswith(query):
        rank = 3
    elif query in normalized_username:
        rank = 4
    elif query in normalized_name:
        rank = 5
    else:
        rank = 6

    return rank, normalized_name, chat.id


def to_message_info(msg: object, *, default_chat_id: int, default_chat_name: str) -> MessageInfo:
    sender = getattr(msg, "sender", None)
    sender_name = ""
    sender_id = getattr(msg, "sender_id", None)
    if sender is not None:
        sender_name = entity_name(sender)

    chat = getattr(msg, "chat", None)
    chat_name = default_chat_name
    if chat is not None:
        chat_name = entity_name(chat)

    reply_to = getattr(msg, "reply_to", None)
    reply_to_message_id = getattr(reply_to, "reply_to_msg_id", None)

    date = getattr(msg, "date", datetime.now(UTC))
    return MessageInfo(
        id=int(getattr(msg, "id", 0)),
        date=to_utc(date),
        sender=sender_name,
        sender_id=sender_id,
        text=(getattr(msg, "text", "") or ""),
        chat_id=int(getattr(msg, "chat_id", None) or default_chat_id),
        chat_name=chat_name,
        reply_to_message_id=reply_to_message_id,
        is_pinned=bool(getattr(msg, "pinned", False)),
    )


async def maybe_await(value: object) -> None:
    if hasattr(value, "__await__"):
        await cast(Awaitable[object], value)
