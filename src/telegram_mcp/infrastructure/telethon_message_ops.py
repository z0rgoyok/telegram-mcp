from __future__ import annotations

import re
from typing import Any, cast

from telethon import TelegramClient, functions, types, utils
from telethon.tl.types import InputMessagesFilterPinned

from ..domain.errors import ErrorCode, ToolError
from ..domain.models import (
    ChatActivity,
    ChatSnapshot,
    MediaFile,
    MediaUrlSource,
    MessageContext,
    MessageInfo,
    MessageOrder,
    Page,
    ThreadMessages,
    TimeRange,
)
from .media_proxy import build_proxy_media_url, extract_direct_media_url
from .telethon_chat_ops import load_chat_info
from .telethon_helpers import (
    entity_name,
    extract_message_media,
    require_entity_id,
    require_message_id,
    to_message_info,
)

GLOBAL_SEARCH_DEFAULT_CHAT_ID = 0
INVALID_CHAT_ID = 0
GLOBAL_SENT_CHATS_PAGE_SIZE = 100


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
    default_chat_id = require_entity_id(entity, context="get_messages")

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
    default_chat_id = require_entity_id(entity, context="get_message_context")

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
    default_chat_id = require_entity_id(entity, context="get_thread_messages")

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
    query: str | None,
    chat_id: int | str | None,
    sender_query: str | None,
    limit: int,
    offset_id: int | None,
    time_range: TimeRange | None,
) -> Page[MessageInfo]:
    entity = await client.get_entity(chat_id) if chat_id is not None else None
    default_chat_name = entity_name(entity) if entity is not None else ""
    default_chat_id = (
        require_entity_id(entity, context="search_messages")
        if entity is not None
        else GLOBAL_SEARCH_DEFAULT_CHAT_ID
    )
    normalized_sender = sender_query.casefold() if sender_query else None

    kwargs: dict[str, object] = {"limit": max(limit * 10, limit + 1)}
    if query:
        kwargs["search"] = query
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


async def list_my_sent_chats(
    client: TelegramClient,
    *,
    limit: int,
    offset: int,
    time_range: TimeRange,
) -> Page[ChatActivity]:
    me = await client.get_me()
    my_user_id = require_entity_id(me, context="list_my_sent_chats")
    me_input = await client.get_input_entity(me)
    activities_map: dict[int, ChatActivity] = {}
    offset_id = GLOBAL_SEARCH_DEFAULT_CHAT_ID
    seen_offsets: set[int] = set()
    should_stop = False

    while not should_stop:
        request = functions.messages.SearchRequest(
            peer=types.InputPeerEmpty(),
            q="",
            filter=types.InputMessagesFilterEmpty(),
            min_date=time_range.from_date,
            max_date=time_range.to_date,
            offset_id=offset_id,
            add_offset=0,
            limit=GLOBAL_SENT_CHATS_PAGE_SIZE,
            max_id=0,
            min_id=0,
            hash=0,
            from_id=me_input,
        )
        result = await client(request)
        entities = _entities_map(result)
        payload = cast(Any, result)
        raw_messages = [item for item in payload.messages if _is_message_like(item)]
        if not raw_messages:
            break

        for raw_message in raw_messages:
            message_payload = cast(Any, raw_message)
            message_date = message_payload.date
            if time_range.from_date and message_date < time_range.from_date:
                should_stop = True
                break
            if not time_range.contains(message_date):
                continue

            sender_id = _peer_id(message_payload.from_id if hasattr(message_payload, "from_id") else None)
            if sender_id != my_user_id:
                continue
            chat_id = _peer_id(message_payload.peer_id if hasattr(message_payload, "peer_id") else None)
            if chat_id is None or chat_id == INVALID_CHAT_ID:
                continue

            entity = entities.get(chat_id)
            chat_name = entity_name(entity) if entity is not None else str(chat_id)
            previous = activities_map.get(chat_id)
            if previous is None:
                activities_map[chat_id] = ChatActivity(
                    chat_id=chat_id,
                    chat_name=chat_name,
                    my_messages_count=1,
                    last_my_message_date=message_date,
                    last_my_message_id=message_payload.id,
                )
                continue

            newer_message_seen = message_date > previous.last_my_message_date
            same_time_bigger_id = (
                message_date == previous.last_my_message_date
                and previous.last_my_message_id is not None
                and message_payload.id > previous.last_my_message_id
            )
            activities_map[chat_id] = ChatActivity(
                chat_id=chat_id,
                chat_name=previous.chat_name or chat_name,
                my_messages_count=previous.my_messages_count + 1,
                last_my_message_date=message_date if newer_message_seen else previous.last_my_message_date,
                last_my_message_id=(
                    message_payload.id
                    if newer_message_seen or same_time_bigger_id
                    else previous.last_my_message_id
                ),
            )

        next_offset = cast(Any, raw_messages[-1]).id
        if next_offset in seen_offsets:
            break
        seen_offsets.add(next_offset)
        offset_id = next_offset

    activities = list(activities_map.values())
    activities.sort(
        key=lambda activity: (activity.last_my_message_date, activity.chat_id),
        reverse=True,
    )
    sliced = activities[offset : offset + limit]
    has_more = len(activities) > offset + limit
    next_offset = offset + limit if has_more else None
    return Page(items=sliced, has_more=has_more, next_offset=next_offset)


async def search_mentions_to_me(
    client: TelegramClient,
    *,
    mention: str,
    chat_id: int | str | None,
    limit: int,
    offset_id: int | None,
    time_range: TimeRange | None,
) -> Page[MessageInfo]:
    entity = await client.get_entity(chat_id) if chat_id is not None else None
    default_chat_name = entity_name(entity) if entity is not None else ""
    default_chat_id = (
        require_entity_id(entity, context="search_mentions_to_me")
        if entity is not None
        else GLOBAL_SEARCH_DEFAULT_CHAT_ID
    )
    mention_handle = mention.strip().lstrip("@")
    if not mention_handle:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            "mention cannot be empty",
            {"field": "mention"},
        )
    mention_query = f"@{mention_handle}"

    kwargs: dict[str, object] = {
        "search": mention_query,
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

        if time_range and not time_range.contains(parsed.date):
            continue
        if not _contains_mention(parsed.text, mention_handle):
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
    default_chat_id = require_entity_id(entity, context="get_chat_snapshot")
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


async def get_message_media(
    client: TelegramClient,
    *,
    chat_id: int | str,
    message_id: int,
    max_bytes: int,
    proxy_public_base_url: str,
    proxy_token_secret: str,
    proxy_token_ttl_seconds: int,
) -> MediaFile:
    entity = await client.get_entity(chat_id)
    message = await client.get_messages(entity, ids=message_id)
    if message is None:
        raise ToolError(
            ErrorCode.NOT_FOUND,
            "Message not found",
            {"chat_id": chat_id, "message_id": message_id},
        )

    media = extract_message_media(message)
    if media is None:
        raise ToolError(
            ErrorCode.NOT_FOUND,
            "Message has no media",
            {"chat_id": chat_id, "message_id": message_id},
        )

    known_size_bytes = media.size_bytes
    if known_size_bytes is not None and known_size_bytes > max_bytes:
        raise ToolError(
            ErrorCode.VALIDATION_ERROR,
            "Media exceeds size limit",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "max_bytes": max_bytes,
                "actual_bytes": known_size_bytes,
            },
        )

    normalized_chat_id = require_entity_id(entity, context="get_message_media")
    normalized_message_id = require_message_id(message, context="get_message_media")
    direct_media_url = extract_direct_media_url(message)
    if direct_media_url:
        return MediaFile(
            chat_id=normalized_chat_id,
            message_id=normalized_message_id,
            kind=media.kind,
            mime_type=media.mime_type,
            file_name=media.file_name,
            size_bytes=known_size_bytes,
            content_url=direct_media_url,
            url_source=MediaUrlSource.TELEGRAM,
        )

    proxy_media_url = build_proxy_media_url(
        base_url=proxy_public_base_url,
        chat_id=normalized_chat_id,
        message_id=normalized_message_id,
        secret=proxy_token_secret,
        ttl_seconds=proxy_token_ttl_seconds,
    )

    return MediaFile(
        chat_id=normalized_chat_id,
        message_id=normalized_message_id,
        kind=media.kind,
        mime_type=media.mime_type,
        file_name=media.file_name,
        size_bytes=known_size_bytes,
        content_url=proxy_media_url,
        url_source=MediaUrlSource.PROXY,
    )


def _contains_mention(text: str, mention_handle: str) -> bool:
    if not text or not mention_handle:
        return False

    pattern = re.compile(
        rf"(?<![A-Za-z0-9_])@{re.escape(mention_handle)}(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )
    return pattern.search(text) is not None


def _peer_id(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(utils.get_peer_id(value))
    except (TypeError, ValueError):
        return None


def _is_message_like(value: object) -> bool:
    payload = cast(Any, value)
    return (
        hasattr(payload, "id")
        and isinstance(payload.id, int)
        and hasattr(payload, "date")
        and hasattr(payload, "peer_id")
    )


def _entities_map(result: object) -> dict[int, object]:
    payload = cast(Any, result)
    mapped: dict[int, object] = {}
    for user in payload.users if hasattr(payload, "users") else []:
        peer_id = _peer_id(user)
        if peer_id is not None:
            mapped[peer_id] = user
    for chat in payload.chats if hasattr(payload, "chats") else []:
        peer_id = _peer_id(chat)
        if peer_id is not None:
            mapped[peer_id] = chat
    return mapped
