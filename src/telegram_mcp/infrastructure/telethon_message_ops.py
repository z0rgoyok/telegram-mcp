from __future__ import annotations

import re
from datetime import datetime
from typing import Any, cast

from telethon import TelegramClient, functions, types, utils
from telethon.tl.types import InputMessagesFilterPinned

from ..domain.errors import ErrorCode, ToolError
from ..domain.models import (
    ChatActivity,
    ChatActivitySummary,
    ChatMessagesBatchItem,
    ChatSnapshot,
    MediaFile,
    MediaKind,
    MediaUrlSource,
    MentionChatActivity,
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
MESSAGE_SCAN_MULTIPLIER = 10
PINNED_MESSAGES_LIMIT = 10
PAGE_OVERFETCH_COUNT = 1
REPLY_TARGETS_BATCH_SIZE = 100
ZERO_HASH = 0
ZERO_OFFSET = 0
NO_MAX_ID = 0
NO_MIN_ID = 0


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

    kwargs: dict[str, object] = {"limit": _scan_limit(limit)}
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
        if len(collected) >= limit + PAGE_OVERFETCH_COUNT:
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
        "limit": _scan_limit(limit),
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
        if len(replies) >= limit + PAGE_OVERFETCH_COUNT:
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

    kwargs: dict[str, object] = {"limit": _scan_limit(limit)}
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
        if len(found) >= limit + PAGE_OVERFETCH_COUNT:
            break

    selected = found[:limit]
    has_more = len(found) > limit
    next_page_offset = selected[-1].id if has_more and selected else None
    return Page(items=selected, has_more=has_more, next_offset=next_page_offset)


async def list_my_sent_chats(
    client: TelegramClient,
    *,
    limit: int,
    offset: int,
    time_range: TimeRange,
) -> Page[ChatActivity]:
    activities_map, has_more_source = await _collect_my_sent_activities_page(
        client,
        time_range=time_range,
        offset=offset,
        limit=limit,
    )

    activities = list(activities_map.values())
    activities.sort(
        key=lambda activity: (activity.last_my_message_date, activity.chat_id),
        reverse=True,
    )
    selected = activities[:limit]
    has_more = len(activities) > limit or has_more_source
    next_offset = offset + _scan_limit(limit) if has_more else None
    return Page(items=selected, has_more=has_more, next_offset=next_offset)


async def list_mentions_to_me_chats(
    client: TelegramClient,
    *,
    mention: str,
    limit: int,
    offset: int,
    time_range: TimeRange | None,
) -> Page[MentionChatActivity]:
    mention_handle = _normalize_mention_handle(mention)
    activities_map, has_more_source = await _collect_mentions_activities_page(
        client,
        mention_handle=mention_handle,
        time_range=time_range,
        offset=offset,
        limit=limit,
    )
    activities = list(activities_map.values())
    activities.sort(
        key=lambda activity: (activity.last_mention_date, activity.chat_id),
        reverse=True,
    )
    selected = activities[:limit]
    has_more = len(activities) > limit or has_more_source
    next_offset = offset + _scan_limit(limit) if has_more else None
    return Page(items=selected, has_more=has_more, next_offset=next_offset)


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
    mention_handle = _normalize_mention_handle(mention)
    mention_query = f"@{mention_handle}"

    kwargs: dict[str, object] = {
        "search": mention_query,
        "limit": _scan_limit(limit),
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
        if len(found) >= limit + PAGE_OVERFETCH_COUNT:
            break

    selected = found[:limit]
    has_more = len(found) > limit
    next_page_offset = selected[-1].id if has_more and selected else None
    return Page(items=selected, has_more=has_more, next_offset=next_page_offset)


async def list_replies_to_me(
    client: TelegramClient,
    *,
    chat_id: int | str | None,
    limit: int,
    offset_id: int | None,
    time_range: TimeRange | None,
) -> Page[MessageInfo]:
    entity = await client.get_entity(chat_id) if chat_id is not None else None
    default_chat_name = entity_name(entity) if entity is not None else ""
    default_chat_id = (
        require_entity_id(entity, context="list_replies_to_me")
        if entity is not None
        else GLOBAL_SEARCH_DEFAULT_CHAT_ID
    )
    me = await client.get_me()
    my_user_id = require_entity_id(me, context="list_replies_to_me")

    scan_limit = _scan_limit(limit)
    kwargs: dict[str, object] = {"limit": scan_limit}
    if offset_id is not None:
        kwargs["offset_id"] = offset_id
    if time_range and time_range.to_date:
        kwargs["offset_date"] = time_range.to_date

    scanned_count = 0
    candidates: list[MessageInfo] = []
    reply_ids_by_chat: dict[int, set[int]] = {}
    async for msg in client.iter_messages(entity, **kwargs):
        scanned_count += 1
        parsed = to_message_info(
            msg,
            default_chat_id=default_chat_id,
            default_chat_name=default_chat_name,
        )
        if time_range and not time_range.contains(parsed.date):
            continue
        if parsed.reply_to_message_id is None:
            continue
        candidates.append(parsed)
        reply_ids_by_chat.setdefault(parsed.chat_id, set()).add(parsed.reply_to_message_id)

    reply_cache = await _resolve_reply_targets_to_me(
        client,
        reply_ids_by_chat=reply_ids_by_chat,
        my_user_id=my_user_id,
    )
    found: list[MessageInfo] = []
    for parsed in candidates:
        reply_to_message_id = parsed.reply_to_message_id
        if not isinstance(reply_to_message_id, int):
            continue
        if not reply_cache.get((parsed.chat_id, reply_to_message_id), False):
            continue
        found.append(parsed)
        if len(found) >= limit + PAGE_OVERFETCH_COUNT:
            break

    selected = found[:limit]
    has_more = len(found) > limit or scanned_count >= scan_limit
    next_page_offset = selected[-1].id if has_more and selected else None
    return Page(items=selected, has_more=has_more, next_offset=next_page_offset)


async def get_messages_batch(
    client: TelegramClient,
    *,
    chat_ids: list[int | str],
    limit_per_chat: int,
    time_range: TimeRange | None,
    order: MessageOrder,
    search: str | None,
) -> list[ChatMessagesBatchItem]:
    result: list[ChatMessagesBatchItem] = []
    for chat_id in chat_ids:
        entity = await client.get_entity(chat_id)
        normalized_chat_id = _peer_id(entity)
        if normalized_chat_id is None:
            normalized_chat_id = require_entity_id(entity, context="get_messages_batch")
        page = await get_messages(
            client,
            chat_id=chat_id,
            limit=limit_per_chat,
            offset_id=None,
            time_range=time_range,
            order=order,
            search=search,
        )
        result.append(
            ChatMessagesBatchItem(
                chat_id=normalized_chat_id,
                chat_name=entity_name(entity),
                messages=page.items,
            )
        )
    return result


async def list_media_messages(
    client: TelegramClient,
    *,
    chat_id: int | str | None,
    media_kind: MediaKind | None,
    limit: int,
    offset_id: int | None,
    time_range: TimeRange | None,
) -> Page[MessageInfo]:
    entity = await client.get_entity(chat_id) if chat_id is not None else None
    default_chat_name = entity_name(entity) if entity is not None else ""
    default_chat_id = (
        require_entity_id(entity, context="list_media_messages")
        if entity is not None
        else GLOBAL_SEARCH_DEFAULT_CHAT_ID
    )

    scan_limit = _scan_limit(limit)
    kwargs: dict[str, object] = {"limit": scan_limit}
    if offset_id is not None:
        kwargs["offset_id"] = offset_id
    if time_range and time_range.to_date:
        kwargs["offset_date"] = time_range.to_date

    batch: list[MessageInfo] = []
    async for msg in client.iter_messages(entity, **kwargs):
        batch.append(
            to_message_info(
                msg,
                default_chat_id=default_chat_id,
                default_chat_name=default_chat_name,
            )
        )

    found: list[MessageInfo] = []
    for parsed in batch:
        if time_range and not time_range.contains(parsed.date):
            continue
        if parsed.media is None:
            continue
        if media_kind is not None and parsed.media.kind is not media_kind:
            continue
        found.append(parsed)
        if len(found) >= limit + PAGE_OVERFETCH_COUNT:
            break

    selected = found[:limit]
    has_more = len(found) > limit or len(batch) >= scan_limit
    next_page_offset = selected[-1].id if has_more and selected else None
    return Page(items=selected, has_more=has_more, next_offset=next_page_offset)


async def list_chat_activity_summary(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    mention: str,
    limit: int,
    offset: int,
    time_range: TimeRange,
) -> Page[ChatActivitySummary]:
    mention_handle = _normalize_mention_handle(mention)
    my_sent_activities, my_has_more = await _collect_my_sent_activities_page(
        client,
        time_range=time_range,
        offset=offset,
        limit=limit,
    )
    mention_activities, mention_has_more = await _collect_mentions_activities_page(
        client,
        mention_handle=mention_handle,
        time_range=time_range,
        offset=offset,
        limit=limit,
    )

    all_chat_ids = set(my_sent_activities.keys()) | set(mention_activities.keys())
    dialog_info = await _load_dialog_info_for_chat_ids(
        client,
        dialog_scan_limit=dialog_scan_limit,
        chat_ids=all_chat_ids,
    )
    summaries: list[ChatActivitySummary] = []
    for chat_id in all_chat_ids:
        my_activity = my_sent_activities.get(chat_id)
        mention_activity = mention_activities.get(chat_id)
        dialog = dialog_info.get(chat_id)
        last_activity = _max_datetime(
            my_activity.last_my_message_date if my_activity is not None else None,
            mention_activity.last_mention_date if mention_activity is not None else None,
        )
        if last_activity is None:
            continue

        chat_name = _pick_chat_name(
            primary=my_activity.chat_name if my_activity is not None else None,
            secondary=mention_activity.chat_name if mention_activity is not None else None,
            fallback=dialog[0] if dialog is not None else str(chat_id),
        )
        summaries.append(
            ChatActivitySummary(
                chat_id=chat_id,
                chat_name=chat_name,
                my_messages_count=my_activity.my_messages_count if my_activity is not None else 0,
                mentions_to_me_count=mention_activity.mentions_count if mention_activity is not None else 0,
                unread_count=dialog[1] if dialog is not None else 0,
                last_activity=last_activity,
                last_my_message_date=(
                    my_activity.last_my_message_date if my_activity is not None else None
                ),
                last_mention_date=(
                    mention_activity.last_mention_date if mention_activity is not None else None
                ),
            )
        )

    summaries.sort(key=lambda item: (item.last_activity, item.chat_id), reverse=True)
    selected = summaries[:limit]
    has_more = len(summaries) > limit or my_has_more or mention_has_more
    next_offset = offset + _scan_limit(limit) if has_more else None
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
            limit=PINNED_MESSAGES_LIMIT,
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


def _normalize_mention_handle(mention: str) -> str:
    mention_handle = mention.strip().lstrip("@")
    if mention_handle:
        return mention_handle
    raise ToolError(
        ErrorCode.VALIDATION_ERROR,
        "mention cannot be empty",
        {"field": "mention"},
    )


def _scan_limit(limit: int) -> int:
    return max(limit * MESSAGE_SCAN_MULTIPLIER, limit + PAGE_OVERFETCH_COUNT)


def _build_global_search_request(
    *,
    query: str,
    time_range: TimeRange | None,
    offset: int,
    limit: int,
    from_id: object | None,
    message_filter: object | None = None,
) -> functions.messages.SearchRequest:
    return functions.messages.SearchRequest(
        peer=types.InputPeerEmpty(),
        q=query,
        filter=message_filter or types.InputMessagesFilterEmpty(),
        min_date=time_range.from_date if time_range is not None else None,
        max_date=time_range.to_date if time_range is not None else None,
        offset_id=ZERO_OFFSET,
        add_offset=offset,
        limit=limit,
        max_id=NO_MAX_ID,
        min_id=NO_MIN_ID,
        hash=ZERO_HASH,
        from_id=from_id,
    )


def _extract_message_like_items(result: object) -> list[object]:
    payload = cast(Any, result)
    return [item for item in payload.messages if _is_message_like(item)]


def _message_date(value: object) -> datetime | None:
    payload = cast(Any, value)
    raw_date = payload.date if hasattr(payload, "date") else None
    if isinstance(raw_date, datetime):
        return raw_date
    return None


def _message_text(value: object) -> str:
    payload = cast(Any, value)
    if hasattr(payload, "text") and isinstance(payload.text, str):
        return payload.text
    if hasattr(payload, "message") and isinstance(payload.message, str):
        return payload.message
    return ""


def _pick_chat_name(*, primary: str | None, secondary: str | None, fallback: str) -> str:
    if primary:
        return primary
    if secondary:
        return secondary
    return fallback


def _max_datetime(first: datetime | None, second: datetime | None) -> datetime | None:
    if first is None:
        return second
    if second is None:
        return first
    return first if first >= second else second


async def _load_dialog_info_for_chat_ids(
    client: TelegramClient,
    *,
    dialog_scan_limit: int,
    chat_ids: set[int],
) -> dict[int, tuple[str, int]]:
    if not chat_ids:
        return {}

    result: dict[int, tuple[str, int]] = {}
    missing = set(chat_ids)
    async for dialog in client.iter_dialogs(limit=dialog_scan_limit):
        dialog_id_obj = dialog.id if hasattr(dialog, "id") else None
        if not isinstance(dialog_id_obj, int):
            continue
        if dialog_id_obj not in missing:
            continue

        unread_obj = dialog.unread_count if hasattr(dialog, "unread_count") else 0
        unread_count = unread_obj if isinstance(unread_obj, int) else 0
        dialog_name_obj = dialog.name if hasattr(dialog, "name") else None
        dialog_name = (
            dialog_name_obj
            if isinstance(dialog_name_obj, str) and dialog_name_obj
            else entity_name(dialog.entity)
        )
        result[dialog_id_obj] = (dialog_name, unread_count)
        missing.remove(dialog_id_obj)
        if not missing:
            break
    return result


def _aggregate_my_sent_activities(
    *,
    raw_messages: list[object],
    entities: dict[int, object],
    time_range: TimeRange,
    my_user_id: int,
) -> dict[int, ChatActivity]:
    activities_map: dict[int, ChatActivity] = {}
    for raw_message in raw_messages:
        message_payload = cast(Any, raw_message)
        message_date = _message_date(message_payload)
        if message_date is None:
            continue
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

    return activities_map


async def _collect_my_sent_activities_page(
    client: TelegramClient,
    *,
    time_range: TimeRange,
    offset: int,
    limit: int,
) -> tuple[dict[int, ChatActivity], bool]:
    me = await client.get_me()
    my_user_id = require_entity_id(me, context="list_my_sent_chats")
    me_input = await client.get_input_entity(me)
    search_limit = _scan_limit(limit)
    request = _build_global_search_request(
        query="",
        time_range=time_range,
        offset=offset,
        limit=search_limit,
        from_id=me_input,
    )
    result = await client(request)
    entities = _entities_map(result)
    raw_messages = _extract_message_like_items(result)
    activities_map = _aggregate_my_sent_activities(
        raw_messages=raw_messages,
        entities=entities,
        time_range=time_range,
        my_user_id=my_user_id,
    )
    has_more = len(raw_messages) >= search_limit
    return activities_map, has_more


def _aggregate_mentions_activities(
    *,
    raw_messages: list[object],
    entities: dict[int, object],
    mention_handle: str,
    time_range: TimeRange | None,
) -> dict[int, MentionChatActivity]:
    activities_map: dict[int, MentionChatActivity] = {}
    for raw_message in raw_messages:
        message_payload = cast(Any, raw_message)
        message_date = _message_date(message_payload)
        if message_date is None:
            continue
        if time_range and not time_range.contains(message_date):
            continue
        if not _contains_mention(_message_text(message_payload), mention_handle):
            continue

        chat_id = _peer_id(message_payload.peer_id if hasattr(message_payload, "peer_id") else None)
        if chat_id is None or chat_id == INVALID_CHAT_ID:
            continue

        entity = entities.get(chat_id)
        chat_name = entity_name(entity) if entity is not None else str(chat_id)
        previous = activities_map.get(chat_id)
        if previous is None:
            activities_map[chat_id] = MentionChatActivity(
                chat_id=chat_id,
                chat_name=chat_name,
                mentions_count=1,
                last_mention_date=message_date,
                last_mention_message_id=message_payload.id,
            )
            continue

        newer_message_seen = message_date > previous.last_mention_date
        same_time_bigger_id = (
            message_date == previous.last_mention_date
            and previous.last_mention_message_id is not None
            and message_payload.id > previous.last_mention_message_id
        )
        activities_map[chat_id] = MentionChatActivity(
            chat_id=chat_id,
            chat_name=previous.chat_name or chat_name,
            mentions_count=previous.mentions_count + 1,
            last_mention_date=message_date if newer_message_seen else previous.last_mention_date,
            last_mention_message_id=(
                message_payload.id
                if newer_message_seen or same_time_bigger_id
                else previous.last_mention_message_id
            ),
        )

    return activities_map


async def _collect_mentions_activities_page(
    client: TelegramClient,
    *,
    mention_handle: str,
    time_range: TimeRange | None,
    offset: int,
    limit: int,
) -> tuple[dict[int, MentionChatActivity], bool]:
    mention_query = f"@{mention_handle}"
    search_limit = _scan_limit(limit)
    request = _build_global_search_request(
        query=mention_query,
        time_range=time_range,
        offset=offset,
        limit=search_limit,
        from_id=None,
        message_filter=types.InputMessagesFilterMyMentions(),
    )
    result = await client(request)
    entities = _entities_map(result)
    raw_messages = _extract_message_like_items(result)
    activities_map = _aggregate_mentions_activities(
        raw_messages=raw_messages,
        entities=entities,
        mention_handle=mention_handle,
        time_range=time_range,
    )
    has_more = len(raw_messages) >= search_limit
    return activities_map, has_more


async def _resolve_reply_targets_to_me(
    client: TelegramClient,
    *,
    reply_ids_by_chat: dict[int, set[int]],
    my_user_id: int,
) -> dict[tuple[int, int], bool]:
    reply_cache: dict[tuple[int, int], bool] = {}
    for chat_id, reply_ids in reply_ids_by_chat.items():
        if not reply_ids:
            continue

        entity = await client.get_entity(chat_id)
        sorted_reply_ids = sorted(reply_ids)
        for batch_ids in _chunk_ids(sorted_reply_ids, REPLY_TARGETS_BATCH_SIZE):
            raw_messages = await client.get_messages(entity, ids=batch_ids)
            resolved_ids: set[int] = set()
            for replied_message in _as_message_list(raw_messages):
                message_id = require_message_id(replied_message, context="list_replies_to_me")
                resolved_ids.add(message_id)
                sender_id_obj = (
                    cast(Any, replied_message).sender_id if hasattr(replied_message, "sender_id") else None
                )
                is_reply_to_me = isinstance(sender_id_obj, int) and sender_id_obj == my_user_id
                reply_cache[(chat_id, message_id)] = is_reply_to_me

            for reply_id in batch_ids:
                if reply_id not in resolved_ids:
                    reply_cache[(chat_id, reply_id)] = False

    return reply_cache


def _as_message_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item is not None]
    return [value]


def _chunk_ids(values: list[int], chunk_size: int) -> list[list[int]]:
    return [values[index : index + chunk_size] for index in range(0, len(values), chunk_size)]


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
