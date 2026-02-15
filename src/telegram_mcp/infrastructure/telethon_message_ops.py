from __future__ import annotations

from telethon import TelegramClient
from telethon.tl.types import InputMessagesFilterPinned

from ..domain.errors import ErrorCode, ToolError
from ..domain.models import (
    ChatSnapshot,
    MessageContext,
    MessageInfo,
    MessageOrder,
    Page,
    ThreadMessages,
    TimeRange,
)
from .telethon_chat_ops import load_chat_info
from .telethon_helpers import entity_name, to_message_info


async def get_messages(
    client: TelegramClient,
    *,
    chat_id: int | str,
    limit: int,
    offset_id: int | None,
    time_range: TimeRange | None,
    order: MessageOrder,
    search: str | None,
) -> Page[MessageInfo]:
    entity = await client.get_entity(chat_id)
    chat_name = entity_name(entity)
    default_chat_id = int(getattr(entity, "id", 0))

    kwargs: dict[str, object] = {"limit": max(limit * 10, limit + 1)}
    if offset_id is not None:
        kwargs["offset_id"] = offset_id
    if search:
        kwargs["search"] = search
    if time_range and time_range.to_date:
        kwargs["offset_date"] = time_range.to_date

    collected: list[MessageInfo] = []
    async for msg in client.iter_messages(entity, **kwargs):
        parsed = to_message_info(
            msg,
            default_chat_id=default_chat_id,
            default_chat_name=chat_name,
        )
        if time_range and not time_range.contains(parsed.date):
            continue
        collected.append(parsed)
        if len(collected) >= limit + 1:
            break

    selected = collected[:limit]
    if order is MessageOrder.ASC:
        selected = list(reversed(selected))

    has_more = len(collected) > limit
    next_offset = collected[limit - 1].id if has_more and len(collected) >= limit else None
    return Page(items=selected, has_more=has_more, next_offset=next_offset)


async def get_message_context(
    client: TelegramClient,
    *,
    chat_id: int | str,
    message_id: int,
    before: int,
    after: int,
) -> MessageContext:
    entity = await client.get_entity(chat_id)
    chat_name = entity_name(entity)
    default_chat_id = int(getattr(entity, "id", 0))

    target_msg = await client.get_messages(entity, ids=message_id)
    if target_msg is None:
        raise ToolError(
            ErrorCode.NOT_FOUND,
            "Message not found",
            {"chat_id": chat_id, "message_id": message_id},
        )

    target = to_message_info(
        target_msg,
        default_chat_id=default_chat_id,
        default_chat_name=chat_name,
    )

    before_items: list[MessageInfo] = []
    if before > 0:
        async for msg in client.iter_messages(entity, offset_id=message_id, limit=before):
            before_items.append(
                to_message_info(
                    msg,
                    default_chat_id=default_chat_id,
                    default_chat_name=chat_name,
                )
            )
        before_items.reverse()

    after_items: list[MessageInfo] = []
    if after > 0:
        async for msg in client.iter_messages(entity, min_id=message_id, limit=after, reverse=True):
            after_items.append(
                to_message_info(
                    msg,
                    default_chat_id=default_chat_id,
                    default_chat_name=chat_name,
                )
            )

    return MessageContext(target=target, before=before_items, after=after_items)


async def get_thread_messages(
    client: TelegramClient,
    *,
    chat_id: int | str,
    root_message_id: int,
    limit: int,
    offset_id: int | None,
) -> ThreadMessages:
    entity = await client.get_entity(chat_id)
    chat_name = entity_name(entity)
    default_chat_id = int(getattr(entity, "id", 0))

    root_msg = await client.get_messages(entity, ids=root_message_id)
    if root_msg is None:
        raise ToolError(
            ErrorCode.NOT_FOUND,
            "Root message not found",
            {"chat_id": chat_id, "root_message_id": root_message_id},
        )

    kwargs: dict[str, object] = {
        "reply_to": root_message_id,
        "limit": max(limit * 10, limit + 1),
    }
    if offset_id is not None:
        kwargs["offset_id"] = offset_id

    replies: list[MessageInfo] = []
    async for msg in client.iter_messages(entity, **kwargs):
        replies.append(
            to_message_info(
                msg,
                default_chat_id=default_chat_id,
                default_chat_name=chat_name,
            )
        )
        if len(replies) >= limit + 1:
            break

    selected = replies[:limit]
    has_more = len(replies) > limit
    next_offset = selected[-1].id if has_more and selected else None
    root = to_message_info(
        root_msg,
        default_chat_id=default_chat_id,
        default_chat_name=chat_name,
    )

    return ThreadMessages(
        root=root,
        page=Page(items=selected, has_more=has_more, next_offset=next_offset),
    )


async def search_messages(
    client: TelegramClient,
    *,
    query: str,
    chat_id: int | str | None,
    sender_query: str | None,
    limit: int,
    offset_id: int | None,
    time_range: TimeRange | None,
) -> Page[MessageInfo]:
    entity = await client.get_entity(chat_id) if chat_id is not None else None
    default_chat_name = entity_name(entity) if entity is not None else ""
    default_chat_id = int(getattr(entity, "id", 0)) if entity is not None else 0
    normalized_sender = sender_query.casefold() if sender_query else None

    kwargs: dict[str, object] = {
        "search": query,
        "limit": max(limit * 10, limit + 1),
    }
    if offset_id is not None:
        kwargs["offset_id"] = offset_id
    if time_range and time_range.to_date:
        kwargs["offset_date"] = time_range.to_date

    found: list[MessageInfo] = []
    async for msg in client.iter_messages(entity, **kwargs):
        parsed = to_message_info(
            msg,
            default_chat_id=default_chat_id,
            default_chat_name=default_chat_name,
        )

        if normalized_sender and normalized_sender not in parsed.sender.casefold():
            continue
        if time_range and not time_range.contains(parsed.date):
            continue

        found.append(parsed)
        if len(found) >= limit + 1:
            break

    selected = found[:limit]
    has_more = len(found) > limit
    next_offset = selected[-1].id if has_more and selected else None
    return Page(items=selected, has_more=has_more, next_offset=next_offset)


async def get_chat_snapshot(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    chat_id: int | str,
    recent_limit: int,
    include_pinned: bool,
) -> ChatSnapshot:
    entity = await client.get_entity(chat_id)
    default_chat_id = int(getattr(entity, "id", 0))
    chat_name = entity_name(entity)

    chat_info = await load_chat_info(
        client,
        dialog_scan_limit=dialog_scan_limit,
        entity=entity,
    )

    recent_messages: list[MessageInfo] = []
    async for msg in client.iter_messages(entity, limit=recent_limit):
        recent_messages.append(
            to_message_info(
                msg,
                default_chat_id=default_chat_id,
                default_chat_name=chat_name,
            )
        )

    pinned_messages: list[MessageInfo] = []
    if include_pinned:
        async for msg in client.iter_messages(
            entity,
            limit=10,
            filter=InputMessagesFilterPinned(),
        ):
            pinned_messages.append(
                to_message_info(
                    msg,
                    default_chat_id=default_chat_id,
                    default_chat_name=chat_name,
                )
            )

    return ChatSnapshot(
        chat=chat_info,
        recent_messages=recent_messages,
        pinned_messages=pinned_messages,
    )
