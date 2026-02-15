from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ChatType(Enum):
    USER = "user"
    GROUP = "group"
    CHANNEL = "channel"


class ChatFilter(Enum):
    ALL = "all"
    CHANNELS = "channels"
    GROUPS = "groups"
    USERS = "users"


@dataclass(frozen=True, slots=True)
class ChatInfo:
    id: int
    type: ChatType
    name: str
    unread_count: int
    username: str | None = None


@dataclass(frozen=True, slots=True)
class MessageInfo:
    id: int
    date: datetime
    sender: str
    text: str
    chat_id: int
    chat_name: str
