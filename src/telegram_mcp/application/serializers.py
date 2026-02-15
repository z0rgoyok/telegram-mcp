from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..domain.models import (
    AuthStatus,
    ChatInfo,
    ChatRef,
    ChatSnapshot,
    HealthStatus,
    MediaFile,
    MessageContext,
    MessageInfo,
    MessageMedia,
    ThreadMessages,
)


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=timezone.utc)
    else:
        normalized = value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def chat_ref_to_dict(chat: ChatRef) -> dict[str, Any]:
    return {
        "id": chat.id,
        "type": chat.type.value,
        "name": chat.name,
        "username": chat.username,
        "unread_count": chat.unread_count,
        "last_activity": iso_utc(chat.last_activity),
    }


def chat_info_to_dict(chat: ChatInfo) -> dict[str, Any]:
    return {
        "id": chat.id,
        "type": chat.type.value,
        "name": chat.name,
        "username": chat.username,
        "unread_count": chat.unread_count,
        "last_activity": iso_utc(chat.last_activity),
    }


def message_to_dict(message: MessageInfo) -> dict[str, Any]:
    return {
        "id": message.id,
        "date": iso_utc(message.date),
        "sender": message.sender,
        "sender_id": message.sender_id,
        "chat_id": message.chat_id,
        "chat_name": message.chat_name,
        "text": message.text,
        "reply_to_message_id": message.reply_to_message_id,
        "is_pinned": message.is_pinned,
        "media": message_media_to_dict(message.media),
    }


def message_media_to_dict(media: MessageMedia | None) -> dict[str, Any] | None:
    if media is None:
        return None
    return {
        "kind": media.kind.value,
        "mime_type": media.mime_type,
        "file_name": media.file_name,
        "size_bytes": media.size_bytes,
        "width": media.width,
        "height": media.height,
        "duration_seconds": media.duration_seconds,
        "has_spoiler": media.has_spoiler,
    }


def media_file_to_dict(media_file: MediaFile) -> dict[str, Any]:
    return {
        "chat_id": media_file.chat_id,
        "message_id": media_file.message_id,
        "kind": media_file.kind.value,
        "mime_type": media_file.mime_type,
        "file_name": media_file.file_name,
        "size_bytes": media_file.size_bytes,
        "content_url": media_file.content_url,
        "url_source": media_file.url_source.value,
    }


def context_to_dict(context: MessageContext) -> dict[str, Any]:
    return {
        "target": message_to_dict(context.target),
        "before": [message_to_dict(item) for item in context.before],
        "after": [message_to_dict(item) for item in context.after],
    }


def thread_to_dict(thread: ThreadMessages) -> dict[str, Any]:
    return {
        "root_message": message_to_dict(thread.root),
        "messages": [message_to_dict(item) for item in thread.page.items],
    }


def snapshot_to_dict(snapshot: ChatSnapshot) -> dict[str, Any]:
    return {
        "chat": chat_info_to_dict(snapshot.chat),
        "recent_messages": [message_to_dict(item) for item in snapshot.recent_messages],
        "pinned_messages": [message_to_dict(item) for item in snapshot.pinned_messages],
    }


def auth_status_to_dict(status: AuthStatus) -> dict[str, Any]:
    return {
        "connected": status.connected,
        "authorized": status.authorized,
        "user_id": status.user_id,
        "name": status.name,
        "username": status.username,
    }


def health_to_dict(status: HealthStatus) -> dict[str, Any]:
    return {
        "status": status.status,
        "connected": status.connected,
        "authorized": status.authorized,
    }
