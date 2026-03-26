from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")


class ChatType(str, Enum):
    USER = "user"
    GROUP = "group"
    CHANNEL = "channel"


class ChatFilter(str, Enum):
    ALL = "all"
    CHANNELS = "channels"
    GROUPS = "groups"
    USERS = "users"


class MembershipAction(str, Enum):
    UNSUBSCRIBED = "unsubscribed"
    LEFT = "left"


class MessageOrder(str, Enum):
    DESC = "desc"
    ASC = "asc"


class MediaKind(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"
    VOICE = "voice"
    ANIMATION = "animation"
    UNKNOWN = "unknown"


class MediaUrlSource(str, Enum):
    TELEGRAM = "telegram"
    PROXY = "proxy"


class ReactionKind(str, Enum):
    EMOJI = "emoji"
    CUSTOM_EMOJI = "custom_emoji"
    PAID = "paid"
    UNKNOWN = "unknown"


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class TimeRange:
    from_date: datetime | None = None
    to_date: datetime | None = None

    def __post_init__(self) -> None:
        normalized_from = to_utc(self.from_date) if self.from_date else None
        normalized_to = to_utc(self.to_date) if self.to_date else None
        object.__setattr__(self, "from_date", normalized_from)
        object.__setattr__(self, "to_date", normalized_to)
        if normalized_from and normalized_to and normalized_from > normalized_to:
            raise ValueError("from_date cannot be later than to_date")

    def contains(self, value: datetime) -> bool:
        point = to_utc(value)
        if self.from_date and point < self.from_date:
            return False
        if self.to_date and point > self.to_date:
            return False
        return True


@dataclass(frozen=True, slots=True)
class ChatInfo:
    id: int
    type: ChatType
    name: str
    unread_count: int
    username: str | None = None
    last_activity: datetime | None = None


@dataclass(frozen=True, slots=True)
class ChatRef:
    id: int
    type: ChatType
    name: str
    username: str | None = None
    unread_count: int = 0
    last_activity: datetime | None = None


@dataclass(frozen=True, slots=True)
class ChatActionResult:
    chat_id: int
    chat_name: str
    chat_type: ChatType
    action: MembershipAction


@dataclass(frozen=True, slots=True)
class ChatActivity:
    chat_id: int
    chat_name: str
    my_messages_count: int
    last_my_message_date: datetime
    last_my_message_id: int | None = None


@dataclass(frozen=True, slots=True)
class MentionChatActivity:
    chat_id: int
    chat_name: str
    mentions_count: int
    last_mention_date: datetime
    last_mention_message_id: int | None = None


@dataclass(frozen=True, slots=True)
class MessageInfo:
    id: int
    date: datetime
    sender: str
    text: str
    chat_id: int
    chat_name: str
    sender_id: int | None = None
    reply_to_message_id: int | None = None
    is_pinned: bool = False
    media: MessageMedia | None = None
    reactions: list[MessageReaction] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MessageMedia:
    kind: MediaKind
    mime_type: str | None = None
    file_name: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None
    has_spoiler: bool = False


@dataclass(frozen=True, slots=True)
class MessageReaction:
    kind: ReactionKind
    count: int
    chosen: bool = False
    emoji: str | None = None
    custom_emoji_id: int | None = None


@dataclass(frozen=True, slots=True)
class MediaFile:
    chat_id: int
    message_id: int
    kind: MediaKind
    content_url: str
    url_source: MediaUrlSource
    mime_type: str | None = None
    file_name: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class ExportFile:
    content_url: str
    file_name: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ExportedMessage:
    message: MessageInfo
    media_file: MediaFile | None = None


@dataclass(frozen=True, slots=True)
class ChatExport:
    chat: ChatInfo
    messages: list[ExportedMessage]


@dataclass(frozen=True, slots=True)
class MessageRef:
    chat_id: int
    message_id: int


@dataclass(frozen=True, slots=True)
class MessageContext:
    target: MessageInfo
    before: list[MessageInfo]
    after: list[MessageInfo]


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: list[T]
    has_more: bool
    next_offset: int | None = None


@dataclass(frozen=True, slots=True)
class ThreadMessages:
    root: MessageInfo
    page: Page[MessageInfo]


@dataclass(frozen=True, slots=True)
class ChatSnapshot:
    chat: ChatInfo
    recent_messages: list[MessageInfo]
    pinned_messages: list[MessageInfo]


@dataclass(frozen=True, slots=True)
class DialogFilterInfo:
    id: int
    title: str
    kind: str
    peer_count: int


@dataclass(frozen=True, slots=True)
class ChatMessagesBatchItem:
    chat_id: int
    chat_name: str
    messages: list[MessageInfo]


@dataclass(frozen=True, slots=True)
class ChatActivitySummary:
    chat_id: int
    chat_name: str
    my_messages_count: int
    mentions_to_me_count: int
    unread_count: int
    last_activity: datetime
    last_my_message_date: datetime | None = None
    last_mention_date: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuthStatus:
    connected: bool
    authorized: bool
    user_id: int | None = None
    name: str | None = None
    username: str | None = None


@dataclass(frozen=True, slots=True)
class HealthStatus:
    status: str
    connected: bool
    authorized: bool
