from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    AuthStatus,
    ChatActivity,
    ChatFilter,
    ChatRef,
    ChatSnapshot,
    HealthStatus,
    MediaFile,
    MessageContext,
    MessageInfo,
    MessageOrder,
    Page,
    ThreadMessages,
    TimeRange,
)


class TelegramReader(ABC):
    @abstractmethod
    async def list_dialogs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        chat_filter: ChatFilter = ChatFilter.ALL,
        query: str | None = None,
        unread_only: bool = False,
    ) -> Page[ChatRef]:
        raise NotImplementedError

    @abstractmethod
    async def list_unread_dialogs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[ChatRef]:
        raise NotImplementedError

    @abstractmethod
    async def list_my_sent_chats(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        time_range: TimeRange,
    ) -> Page[ChatActivity]:
        raise NotImplementedError

    @abstractmethod
    async def resolve_chat(
        self,
        *,
        query: str,
        limit: int = 20,
    ) -> list[ChatRef]:
        raise NotImplementedError

    @abstractmethod
    async def get_messages(
        self,
        *,
        chat_id: int | str,
        limit: int = 50,
        offset_id: int | None = None,
        time_range: TimeRange | None = None,
        order: MessageOrder = MessageOrder.DESC,
        search: str | None = None,
    ) -> Page[MessageInfo]:
        raise NotImplementedError

    @abstractmethod
    async def get_message_context(
        self,
        *,
        chat_id: int | str,
        message_id: int,
        before: int,
        after: int,
    ) -> MessageContext:
        raise NotImplementedError

    @abstractmethod
    async def get_thread_messages(
        self,
        *,
        chat_id: int | str,
        root_message_id: int,
        limit: int = 50,
        offset_id: int | None = None,
    ) -> ThreadMessages:
        raise NotImplementedError

    @abstractmethod
    async def search_messages(
        self,
        *,
        query: str | None = None,
        chat_id: int | str | None = None,
        sender_query: str | None = None,
        limit: int = 20,
        offset_id: int | None = None,
        time_range: TimeRange | None = None,
    ) -> Page[MessageInfo]:
        raise NotImplementedError

    @abstractmethod
    async def search_mentions_to_me(
        self,
        *,
        mention: str,
        chat_id: int | str | None = None,
        limit: int = 20,
        offset_id: int | None = None,
        time_range: TimeRange | None = None,
    ) -> Page[MessageInfo]:
        raise NotImplementedError

    @abstractmethod
    async def get_chat_snapshot(
        self,
        *,
        chat_id: int | str,
        recent_limit: int,
        include_pinned: bool,
    ) -> ChatSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def get_message_media(
        self,
        *,
        chat_id: int | str,
        message_id: int,
    ) -> MediaFile:
        raise NotImplementedError

    @abstractmethod
    async def get_auth_status(self) -> AuthStatus:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        raise NotImplementedError
