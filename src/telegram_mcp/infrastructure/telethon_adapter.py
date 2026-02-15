from __future__ import annotations

import sys
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

from ..domain.models import ChatFilter, ChatInfo, ChatType, MessageInfo
from .config import Settings


class TelethonAdapter:
    """TelegramReader implementation backed by Telethon."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = TelegramClient(
            str(settings.session_path),
            settings.api_id,
            settings.api_hash,
            flood_sleep_threshold=30,
        )

    async def connect(self) -> None:
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError(
                "Telegram session not authorized. "
                "Run the auth service first: "
                "docker compose --profile auth run --rm auth"
            )
        me = await self._client.get_me()
        print(f"Connected as {me.first_name} (id={me.id})", file=sys.stderr)

    async def disconnect(self) -> None:
        await self._client.disconnect()

    async def list_dialogs(
        self,
        limit: int = 50,
        filter: ChatFilter = ChatFilter.ALL,
    ) -> list[ChatInfo]:
        result: list[ChatInfo] = []
        async for dialog in self._client.iter_dialogs(limit=limit):
            chat_type = _entity_to_chat_type(dialog.entity)
            if not _matches_filter(chat_type, filter):
                continue
            username = getattr(dialog.entity, "username", None)
            result.append(
                ChatInfo(
                    id=dialog.id,
                    type=chat_type,
                    name=dialog.name,
                    unread_count=dialog.unread_count,
                    username=username,
                )
            )
        return result

    async def get_messages(
        self,
        chat_id: int | str,
        limit: int = 50,
        offset_date: datetime | None = None,
        search: str | None = None,
    ) -> list[MessageInfo]:
        entity = await self._client.get_entity(chat_id)
        chat_name = _entity_name(entity)

        kwargs: dict = {"limit": limit}
        if offset_date is not None:
            kwargs["offset_date"] = offset_date
        if search:
            kwargs["search"] = search

        messages: list[MessageInfo] = []
        async for msg in self._client.iter_messages(entity, **kwargs):
            sender_name = ""
            if msg.sender:
                sender_name = _entity_name(msg.sender)

            messages.append(
                MessageInfo(
                    id=msg.id,
                    date=msg.date,
                    sender=sender_name,
                    text=msg.text or "",
                    chat_id=chat_id if isinstance(chat_id, int) else msg.chat_id,
                    chat_name=chat_name,
                )
            )
        return messages

    async def search_global(
        self,
        query: str,
        chat_id: int | str | None = None,
        limit: int = 20,
    ) -> list[MessageInfo]:
        entity = None
        if chat_id is not None:
            entity = await self._client.get_entity(chat_id)

        messages: list[MessageInfo] = []
        async for msg in self._client.iter_messages(
            entity, search=query, limit=limit
        ):
            sender_name = ""
            if msg.sender:
                sender_name = _entity_name(msg.sender)

            chat_name = ""
            if msg.chat:
                chat_name = _entity_name(msg.chat)

            messages.append(
                MessageInfo(
                    id=msg.id,
                    date=msg.date,
                    sender=sender_name,
                    text=msg.text or "",
                    chat_id=msg.chat_id or 0,
                    chat_name=chat_name,
                )
            )
        return messages


def _entity_to_chat_type(entity: object) -> ChatType:
    if isinstance(entity, Channel):
        return ChatType.CHANNEL if entity.broadcast else ChatType.GROUP
    if isinstance(entity, Chat):
        return ChatType.GROUP
    return ChatType.USER


def _matches_filter(chat_type: ChatType, filter: ChatFilter) -> bool:
    if filter is ChatFilter.ALL:
        return True
    return filter.value == chat_type.value + "s"


def _entity_name(entity: object) -> str:
    if isinstance(entity, User):
        parts = [entity.first_name or "", entity.last_name or ""]
        return " ".join(p for p in parts if p) or str(entity.id)
    return getattr(entity, "title", "") or getattr(entity, "name", "") or str(getattr(entity, "id", ""))
