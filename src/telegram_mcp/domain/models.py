from __future__ import annotations

from dataclasses import dataclass
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


class MessageOrder(str, Enum):
    DESC = "desc"
    ASC = "asc"


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
