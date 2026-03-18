from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, cast

from telethon import TelegramClient, functions
from telethon.errors import RPCError
from telethon.tl.types import DialogFilter, DialogFilterChatlist
from telethon.utils import get_peer_id

from ..domain.errors import ErrorCode, ToolError
from ..domain.models import ChatFilter, ChatInfo, ChatRef, DialogFilterInfo, Page, to_utc
from .telethon_helpers import (
    chat_matches_query,
    chat_rank,
    entity_name,
    entity_to_chat_type,
    entity_username,
    marked_chat_id,
    matches_filter,
    require_entity_id,
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
    folder: int | None,
    dialog_filter: int | str | None,
) -> Page[ChatRef]:
    query_text = query.casefold() if query else None
    if query_text or dialog_filter is not None:
        chats = await _search_dialogs(
            client,
            dialog_scan_limit=dialog_scan_limit,
            limit=limit,
            offset=offset,
            chat_filter=chat_filter,
            query_text=query_text,
            unread_only=unread_only,
            folder=folder,
            dialog_filter=dialog_filter,
        )
    else:
        required = offset + limit + 1
        chats = []

        async for dialog in client.iter_dialogs(limit=dialog_scan_limit, folder=folder):
            chat = _chat_ref_from_dialog(dialog)
            if not matches_filter(chat.type, chat_filter):
                continue
            if unread_only and chat.unread_count <= 0:
                continue

            chats.append(chat)
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
    folder: int | None,
) -> Page[ChatRef]:
    chats: list[ChatRef] = []
    async for dialog in client.iter_dialogs(limit=dialog_scan_limit, folder=folder):
        if dialog.unread_count <= 0:
            continue

        chats.append(
            ChatRef(
                id=dialog.id,
                type=entity_to_chat_type(dialog.entity),
                name=dialog.name or entity_name(dialog.entity),
                username=entity_username(dialog.entity),
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


async def list_dialog_filters(client: TelegramClient) -> list[DialogFilterInfo]:
    filters_result = await client(functions.messages.GetDialogFiltersRequest())
    filters = filters_result.filters if hasattr(filters_result, "filters") else []

    items: list[DialogFilterInfo] = []
    for item in filters:
        if not isinstance(item, (DialogFilter, DialogFilterChatlist)):
            continue
        items.append(
            DialogFilterInfo(
                id=item.id,
                title=_dialog_filter_title(item),
                kind=_dialog_filter_kind(item),
                peer_count=len(_dialog_filter_peers(item)),
            )
        )
    return items


async def resolve_chat(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    query: str,
    limit: int,
    dialog_filter: int | str | None,
) -> list[ChatRef]:
    query_text = query.strip().casefold().lstrip("@")
    result: dict[int, ChatRef] = {}

    if dialog_filter is None and (query.startswith("@") or query.lstrip("-").isdigit()):
        try:
            entity = await client.get_entity(query)
            ref = ChatRef(
                id=marked_chat_id(entity, context="resolve_chat"),
                type=entity_to_chat_type(entity),
                name=entity_name(entity),
                username=entity_username(entity),
                unread_count=0,
                last_activity=None,
            )
            result[ref.id] = ref
        except (RPCError, ValueError, TypeError, ToolError):
            logger.debug("Direct resolve failed for %s", query)

    if dialog_filter is None:
        async for dialog in client.iter_dialogs(limit=dialog_scan_limit):
            chat = _chat_ref_from_dialog(dialog)
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

        extra_matches = await _search_filter_peer_refs(
            client,
            query_text=query_text,
            dialog_filter=None,
            known_dialogs=result,
        )
        result.update(extra_matches)
    else:
        filtered_matches = await _search_filter_peer_refs(
            client,
            query_text=query_text,
            dialog_filter=dialog_filter,
            known_dialogs={},
        )
        result.update(filtered_matches)

    ranked = sorted(result.values(), key=lambda item: chat_rank(item, query_text))
    return ranked[:limit]


async def load_chat_info(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    entity: object,
) -> ChatInfo:
    target_id = require_entity_id(entity, context="load_chat_info")
    async for dialog in client.iter_dialogs(limit=dialog_scan_limit):
        if dialog.id == target_id:
            return ChatInfo(
                id=dialog.id,
                type=entity_to_chat_type(dialog.entity),
                name=dialog.name or entity_name(dialog.entity),
                username=entity_username(dialog.entity),
                unread_count=dialog.unread_count,
                last_activity=to_utc(dialog.date) if dialog.date else None,
            )

    return ChatInfo(
        id=target_id,
        type=entity_to_chat_type(entity),
        name=entity_name(entity),
        username=entity_username(entity),
        unread_count=0,
        last_activity=None,
    )


def _chat_ref_from_dialog(dialog: object) -> ChatRef:
    payload = cast(Any, dialog)
    return ChatRef(
        id=require_entity_id(payload, context="dialog_ref"),
        type=entity_to_chat_type(payload.entity),
        name=payload.name or entity_name(payload.entity),
        username=entity_username(payload.entity),
        unread_count=payload.unread_count,
        last_activity=to_utc(payload.date) if payload.date else None,
    )


async def _search_dialogs(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    limit: int,
    offset: int,
    chat_filter: ChatFilter,
    query_text: str | None,
    unread_only: bool,
    folder: int | None,
    dialog_filter: int | str | None,
) -> list[ChatRef]:
    dialog_refs: dict[int, ChatRef] = {}

    async for dialog in client.iter_dialogs(limit=dialog_scan_limit, folder=folder):
        chat = _chat_ref_from_dialog(dialog)
        if not matches_filter(chat.type, chat_filter):
            continue
        if unread_only and chat.unread_count <= 0:
            continue
        if query_text and not chat_matches_query(
            query=query_text,
            chat_id=chat.id,
            name=chat.name,
            username=chat.username,
        ):
            continue
        dialog_refs[chat.id] = chat

    required = offset + limit + 1
    if dialog_filter is not None:
        ordered_refs = await _load_filter_chats(
            client,
            dialog_filter=dialog_filter,
            query_text=query_text,
            chat_filter=chat_filter,
            unread_only=unread_only,
            known_dialogs=dialog_refs,
        )
        return ordered_refs[:required]

    if query_text is None:
        return list(dialog_refs.values())[:required]

    extra_refs = await _search_filter_peer_refs(
        client,
        query_text=query_text,
        dialog_filter=None,
        known_dialogs=dialog_refs,
    )
    combined = list(dialog_refs.values()) + [
        ref for chat_id, ref in extra_refs.items() if chat_id not in dialog_refs
    ]
    combined.sort(key=lambda item: chat_rank(item, query_text))
    return combined[:required]


async def _load_filter_chats(
    client: TelegramClient,
    *,
    dialog_filter: int | str,
    query_text: str | None,
    chat_filter: ChatFilter,
    unread_only: bool,
    known_dialogs: dict[int, ChatRef],
) -> list[ChatRef]:
    peers = await _get_dialog_filter_peers(client, dialog_filter=dialog_filter)
    items: list[ChatRef] = []
    seen: set[int] = set()
    for peer in peers:
        chat = await _resolve_peer_chat_ref(client, peer=peer, known_dialogs=known_dialogs)
        if chat is None or chat.id in seen:
            continue
        if not matches_filter(chat.type, chat_filter):
            continue
        if unread_only and chat.unread_count <= 0:
            continue
        if query_text and not chat_matches_query(
            query=query_text,
            chat_id=chat.id,
            name=chat.name,
            username=chat.username,
        ):
            continue
        seen.add(chat.id)
        items.append(chat)
    if query_text:
        items.sort(key=lambda item: chat_rank(item, query_text))
    return items


async def _search_filter_peer_refs(
    client: TelegramClient,
    *,
    query_text: str,
    dialog_filter: int | str | None,
    known_dialogs: dict[int, ChatRef],
) -> dict[int, ChatRef]:
    peers = await _get_dialog_filter_peers(client, dialog_filter=dialog_filter)
    result: dict[int, ChatRef] = {}
    for peer in peers:
        chat = await _resolve_peer_chat_ref(client, peer=peer, known_dialogs=known_dialogs)
        if chat is None:
            continue
        if not chat_matches_query(
            query=query_text,
            chat_id=chat.id,
            name=chat.name,
            username=chat.username,
        ):
            continue
        result[chat.id] = chat
    return result


async def _resolve_peer_chat_ref(
    client: TelegramClient,
    *,
    peer: object,
    known_dialogs: dict[int, ChatRef],
) -> ChatRef | None:
    peer_chat_id = _peer_chat_id(peer)
    if peer_chat_id is not None and peer_chat_id in known_dialogs:
        return known_dialogs[peer_chat_id]

    try:
        entity = await client.get_entity(cast(Any, peer))
    except (RPCError, ValueError, TypeError):
        logger.debug("Skipping unresolved dialog filter peer %s", peer)
        return None

    chat_id = marked_chat_id(entity, context="dialog_filter_peer")
    if chat_id in known_dialogs:
        return known_dialogs[chat_id]

    return ChatRef(
        id=chat_id,
        type=entity_to_chat_type(entity),
        name=entity_name(entity),
        username=entity_username(entity),
        unread_count=0,
        last_activity=None,
    )


async def _get_dialog_filter_peers(
    client: TelegramClient,
    *,
    dialog_filter: int | str | None,
) -> list[object]:
    filters_result = await client(functions.messages.GetDialogFiltersRequest())
    filters = filters_result.filters if hasattr(filters_result, "filters") else []
    selected_filters = (
        [_select_dialog_filter(filters, dialog_filter)]
        if dialog_filter is not None
        else [
            item
            for item in filters
            if isinstance(item, (DialogFilter, DialogFilterChatlist))
        ]
    )

    peers: list[object] = []
    seen: set[int] = set()
    for item in selected_filters:
        for peer in _dialog_filter_peers(item):
            peer_chat_id = _peer_chat_id(peer)
            if peer_chat_id is None or peer_chat_id in seen:
                continue
            seen.add(peer_chat_id)
            peers.append(peer)
    return peers


def _select_dialog_filter(filters: Sequence[object], dialog_filter: int | str) -> object:
    for item in filters:
        if not isinstance(item, (DialogFilter, DialogFilterChatlist)):
            continue
        title = _dialog_filter_title(item)
        filter_id = item.id if hasattr(item, "id") else None
        if isinstance(dialog_filter, int) and filter_id == dialog_filter:
            return item
        if isinstance(dialog_filter, str) and title.casefold() == dialog_filter.casefold():
            return item
    raise ToolError(
        ErrorCode.NOT_FOUND,
        "Dialog filter not found",
        {"dialog_filter": dialog_filter},
    )


def _dialog_filter_title(value: object) -> str:
    title = getattr(value, "title", None)
    text = getattr(title, "text", None)
    if isinstance(text, str) and text:
        return text
    return str(getattr(value, "id", "unknown"))


def _dialog_filter_peers(value: object) -> list[object]:
    peers: list[object] = []
    for field in ("pinned_peers", "include_peers"):
        field_value = getattr(value, field, None)
        if isinstance(field_value, list):
            peers.extend(field_value)
    return peers


def _dialog_filter_kind(value: object) -> str:
    if isinstance(value, DialogFilterChatlist):
        return "chatlist"
    if isinstance(value, DialogFilter):
        return "filter"
    return "unknown"


def _peer_chat_id(peer: object) -> int | None:
    try:
        return int(get_peer_id(peer))
    except (AttributeError, TypeError, ValueError):
        return None
