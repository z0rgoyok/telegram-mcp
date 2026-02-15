from __future__ import annotations

import logging

from telethon import TelegramClient
from telethon.errors import RPCError

from ..domain.models import ChatFilter, ChatInfo, ChatRef, Page, to_utc
from .telethon_helpers import (
    chat_matches_query,
    chat_rank,
    entity_name,
    entity_to_chat_type,
    matches_filter,
)

logger = logging.getLogger(__name__)


async def list_dialogs(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    limit: int,
    offset: int,
    chat_filter: ChatFilter,
    query: str | None,
    unread_only: bool,
) -> Page[ChatRef]:
    required = offset + limit + 1
    query_text = query.casefold() if query else None
    chats: list[ChatRef] = []

    async for dialog in client.iter_dialogs(limit=dialog_scan_limit):
        chat_type = entity_to_chat_type(dialog.entity)
        if not matches_filter(chat_type, chat_filter):
            continue
        if unread_only and dialog.unread_count <= 0:
            continue

        name = dialog.name or entity_name(dialog.entity)
        username = getattr(dialog.entity, "username", None)
        if query_text and not chat_matches_query(
            query=query_text,
            chat_id=dialog.id,
            name=name,
            username=username,
        ):
            continue

        chats.append(
            ChatRef(
                id=dialog.id,
                type=chat_type,
                name=name,
                username=username,
                unread_count=dialog.unread_count,
                last_activity=to_utc(dialog.date) if dialog.date else None,
            )
        )
        if len(chats) >= required:
            break

    sliced = chats[offset: offset + limit]
    has_more = len(chats) > offset + limit
    next_offset = offset + limit if has_more else None
    return Page(items=sliced, has_more=has_more, next_offset=next_offset)


async def list_unread_dialogs(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    limit: int,
    offset: int,
) -> Page[ChatRef]:
    chats: list[ChatRef] = []
    async for dialog in client.iter_dialogs(limit=dialog_scan_limit):
        if dialog.unread_count <= 0:
            continue

        chats.append(
            ChatRef(
                id=dialog.id,
                type=entity_to_chat_type(dialog.entity),
                name=dialog.name or entity_name(dialog.entity),
                username=getattr(dialog.entity, "username", None),
                unread_count=dialog.unread_count,
                last_activity=to_utc(dialog.date) if dialog.date else None,
            )
        )

    chats.sort(
        key=lambda chat: (
            -chat.unread_count,
            -chat.last_activity.timestamp() if chat.last_activity else float("inf"),
            chat.id,
        )
    )

    sliced = chats[offset: offset + limit]
    has_more = len(chats) > offset + limit
    next_offset = offset + limit if has_more else None
    return Page(items=sliced, has_more=has_more, next_offset=next_offset)


async def resolve_chat(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    query: str,
    limit: int,
) -> list[ChatRef]:
    query_text = query.strip().casefold().lstrip("@")
    result: dict[int, ChatRef] = {}

    if query.startswith("@") or query.lstrip("-").isdigit():
        try:
            entity = await client.get_entity(query)
            ref = ChatRef(
                id=getattr(entity, "id", 0),
                type=entity_to_chat_type(entity),
                name=entity_name(entity),
                username=getattr(entity, "username", None),
                unread_count=0,
                last_activity=None,
            )
            result[ref.id] = ref
        except (RPCError, ValueError, TypeError):
            logger.debug("Direct resolve failed for %s", query)

    async for dialog in client.iter_dialogs(limit=dialog_scan_limit):
        chat = ChatRef(
            id=dialog.id,
            type=entity_to_chat_type(dialog.entity),
            name=dialog.name or entity_name(dialog.entity),
            username=getattr(dialog.entity, "username", None),
            unread_count=dialog.unread_count,
            last_activity=to_utc(dialog.date) if dialog.date else None,
        )
        if not chat_matches_query(
            query=query_text,
            chat_id=chat.id,
            name=chat.name,
            username=chat.username,
        ):
            continue
        result[chat.id] = chat
        if len(result) >= max(limit * 2, limit):
            break

    ranked = sorted(result.values(), key=lambda item: chat_rank(item, query_text))
    return ranked[:limit]


async def load_chat_info(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    entity: object,
) -> ChatInfo:
    entity_id = getattr(entity, "id", None)
    async for dialog in client.iter_dialogs(limit=dialog_scan_limit):
        if dialog.id == entity_id:
            return ChatInfo(
                id=dialog.id,
                type=entity_to_chat_type(dialog.entity),
                name=dialog.name or entity_name(dialog.entity),
                username=getattr(dialog.entity, "username", None),
                unread_count=dialog.unread_count,
                last_activity=to_utc(dialog.date) if dialog.date else None,
            )

    return ChatInfo(
        id=entity_id if isinstance(entity_id, int) else 0,
        type=entity_to_chat_type(entity),
        name=entity_name(entity),
        username=getattr(entity, "username", None),
        unread_count=0,
        last_activity=None,
    )
