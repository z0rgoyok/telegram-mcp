from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import ChatFilter, ChatInfo, MessageInfo


class TelegramReader(Protocol):
    async def list_dialogs(
        self,
        limit: int = 50,
        filter: ChatFilter = ChatFilter.ALL,
    ) -> list[ChatInfo]: ...

    async def get_messages(
        self,
        chat_id: int | str,
        limit: int = 50,
        offset_date: datetime | None = None,
        search: str | None = None,
    ) -> list[MessageInfo]: ...

    async def search_global(
        self,
        query: str,
        chat_id: int | str | None = None,
        limit: int = 20,
    ) -> list[MessageInfo]: ...
