from __future__ import annotations

from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Any, cast

from telethon.tl.types import Channel, Chat, User
from telethon.utils import get_peer_id

from ..domain.errors import ErrorCode, ToolError
from ..domain.models import (
    ChatFilter,
    ChatRef,
    ChatType,
    MediaKind,
    MessageInfo,
    MessageMedia,
    to_utc,
)


def entity_to_chat_type(entity: object) -> ChatType:
    if isinstance(entity, Channel):
        return ChatType.CHANNEL if bool(entity.broadcast) else ChatType.GROUP
    if isinstance(entity, Chat):
        return ChatType.GROUP
    return ChatType.USER


def require_entity_id(entity: object, *, context: str) -> int:
    if not hasattr(entity, "id"):
        raise ToolError(
            ErrorCode.PROVIDER_ERROR,
            "Telegram payload missing required id",
            {"context": context},
        )
    entity_id = cast(Any, entity).id
    if not isinstance(entity_id, int):
        raise ToolError(
            ErrorCode.PROVIDER_ERROR,
            "Telegram payload has invalid id type",
            {"context": context, "id": entity_id},
        )
    return entity_id


def marked_chat_id(entity: object, *, context: str) -> int:
    try:
        return int(get_peer_id(entity))
    except (AttributeError, TypeError, ValueError):
        return require_entity_id(entity, context=context)


def require_message_id(message: object, *, context: str) -> int:
    if not hasattr(message, "id"):
        raise ToolError(
            ErrorCode.PROVIDER_ERROR,
            "Telegram message payload missing id",
            {"context": context},
        )
    message_id = cast(Any, message).id
    if not isinstance(message_id, int):
        raise ToolError(
            ErrorCode.PROVIDER_ERROR,
            "Telegram message payload has invalid id type",
            {"context": context, "id": message_id},
        )
    return message_id


def entity_username(entity: object) -> str | None:
    if isinstance(entity, User):
        return entity.username
    if isinstance(entity, Channel):
        return entity.username
    if hasattr(entity, "username"):
        username = cast(Any, entity).username
        return username if isinstance(username, str) else None
    return None


def matches_filter(chat_type: ChatType, chat_filter: ChatFilter) -> bool:
    if chat_filter is ChatFilter.ALL:
        return True
    return chat_filter.value == chat_type.value + "s"


def entity_name(entity: object) -> str:
    if isinstance(entity, User) or hasattr(entity, "first_name") or hasattr(entity, "last_name"):
        first_name_obj = cast(Any, entity).first_name if hasattr(entity, "first_name") else None
        last_name_obj = cast(Any, entity).last_name if hasattr(entity, "last_name") else None
        parts = [
            first_name_obj if isinstance(first_name_obj, str) else "",
            last_name_obj if isinstance(last_name_obj, str) else "",
        ]
        joined = " ".join(part for part in parts if part).strip()
        if joined:
            return joined
        if hasattr(entity, "id"):
            return str(cast(Any, entity).id)
        return "unknown"

    if isinstance(entity, (Channel, Chat)):
        if entity.title:
            return entity.title
        return str(entity.id)

    if hasattr(entity, "title"):
        title = cast(Any, entity).title
        if isinstance(title, str) and title:
            return title
    if hasattr(entity, "name"):
        name = cast(Any, entity).name
        if isinstance(name, str) and name:
            return name
    if hasattr(entity, "id"):
        return str(cast(Any, entity).id)
    return "unknown"


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
    msg_payload = cast(Any, msg)

    sender = msg_payload.sender if hasattr(msg_payload, "sender") else None
    sender_name = ""
    sender_id_obj = msg_payload.sender_id if hasattr(msg_payload, "sender_id") else None
    sender_id = sender_id_obj if isinstance(sender_id_obj, int) else None
    if sender is not None:
        sender_name = entity_name(sender)

    chat = msg_payload.chat if hasattr(msg_payload, "chat") else None
    chat_name = default_chat_name
    if chat is not None:
        chat_name = entity_name(chat)

    reply_to = msg_payload.reply_to if hasattr(msg_payload, "reply_to") else None
    reply_to_message_id_obj = (
        reply_to.reply_to_msg_id
        if reply_to is not None and hasattr(reply_to, "reply_to_msg_id")
        else None
    )
    reply_to_message_id = (
        reply_to_message_id_obj if isinstance(reply_to_message_id_obj, int) else None
    )
    media = extract_message_media(msg)

    raw_date = msg_payload.date if hasattr(msg_payload, "date") else None
    date = raw_date if isinstance(raw_date, datetime) else datetime.now(UTC)
    message_id = require_message_id(msg, context="message_info")
    raw_text = msg_payload.text if hasattr(msg_payload, "text") else ""
    text = raw_text if isinstance(raw_text, str) else ""
    chat_id_obj = msg_payload.chat_id if hasattr(msg_payload, "chat_id") else None
    chat_id = chat_id_obj if isinstance(chat_id_obj, int) else default_chat_id
    raw_pinned = msg_payload.pinned if hasattr(msg_payload, "pinned") else False

    return MessageInfo(
        id=message_id,
        date=to_utc(date),
        sender=sender_name,
        sender_id=sender_id,
        text=text,
        chat_id=chat_id,
        chat_name=chat_name,
        reply_to_message_id=reply_to_message_id,
        is_pinned=bool(raw_pinned),
        media=media,
    )


def extract_message_media(msg: object) -> MessageMedia | None:
    msg_payload = cast(Any, msg)
    file_ref = msg_payload.file if hasattr(msg_payload, "file") else None
    raw_media = msg_payload.media if hasattr(msg_payload, "media") else None
    if file_ref is None and raw_media is None:
        return None

    mime_type_obj = file_ref.mime_type if file_ref is not None and hasattr(file_ref, "mime_type") else None
    file_name_obj = file_ref.name if file_ref is not None and hasattr(file_ref, "name") else None
    size_obj = file_ref.size if file_ref is not None and hasattr(file_ref, "size") else None
    width_obj = file_ref.width if file_ref is not None and hasattr(file_ref, "width") else None
    height_obj = file_ref.height if file_ref is not None and hasattr(file_ref, "height") else None
    duration_obj = (
        file_ref.duration if file_ref is not None and hasattr(file_ref, "duration") else None
    )
    spoiler_obj = raw_media.spoiler if raw_media is not None and hasattr(raw_media, "spoiler") else False

    return MessageMedia(
        kind=_detect_media_kind(msg),
        mime_type=_optional_str(mime_type_obj),
        file_name=_optional_str(file_name_obj),
        size_bytes=_optional_int(size_obj),
        width=_optional_int(width_obj),
        height=_optional_int(height_obj),
        duration_seconds=_optional_int(duration_obj),
        has_spoiler=bool(spoiler_obj),
    )


def _detect_media_kind(msg: object) -> MediaKind:
    msg_payload = cast(Any, msg)
    if hasattr(msg_payload, "photo") and msg_payload.photo is not None:
        return MediaKind.PHOTO
    if hasattr(msg_payload, "video") and msg_payload.video is not None:
        return MediaKind.VIDEO
    if hasattr(msg_payload, "voice") and msg_payload.voice is not None:
        return MediaKind.VOICE
    if hasattr(msg_payload, "audio") and msg_payload.audio is not None:
        return MediaKind.AUDIO
    if hasattr(msg_payload, "sticker") and msg_payload.sticker is not None:
        return MediaKind.STICKER
    if hasattr(msg_payload, "gif") and msg_payload.gif is not None:
        return MediaKind.ANIMATION
    if hasattr(msg_payload, "document") and msg_payload.document is not None:
        return MediaKind.DOCUMENT
    return MediaKind.UNKNOWN


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


async def maybe_await(value: object) -> None:
    if hasattr(value, "__await__"):
        await cast(Awaitable[object], value)
