from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ..domain.models import ExportFile
from ..domain.ports import ChatExportWriter
from .config import Settings
from .media_proxy import build_proxy_export_url

_EXPORT_MIME_TYPE = "application/json"


@dataclass(frozen=True, slots=True)
class StoredExport:
    file_name: str
    mime_type: str
    content: bytes
    expires_at: datetime


class InMemoryChatExportStore(ChatExportWriter):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._items: dict[str, StoredExport] = {}
        self._lock = asyncio.Lock()

    async def write_export_file(
        self,
        *,
        chat_id: int,
        chat_name: str,
        content: bytes,
    ) -> ExportFile:
        export_id = uuid4().hex
        ttl_seconds = self._settings.media_proxy_token_ttl_seconds
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        stored_export = StoredExport(
            file_name=_build_export_file_name(chat_name, chat_id),
            mime_type=_EXPORT_MIME_TYPE,
            content=content,
            expires_at=expires_at,
        )

        async with self._lock:
            self._purge_expired_locked(now=datetime.now(UTC))
            self._items[export_id] = stored_export

        return ExportFile(
            content_url=build_proxy_export_url(
                base_url=self._settings.media_proxy_public_base_url,
                export_id=export_id,
                secret=self._settings.media_proxy_token_secret,
                ttl_seconds=ttl_seconds,
            ),
            file_name=stored_export.file_name,
            mime_type=stored_export.mime_type,
            size_bytes=len(content),
        )

    async def get_export(self, export_id: str) -> StoredExport | None:
        async with self._lock:
            now = datetime.now(UTC)
            self._purge_expired_locked(now=now)
            stored_export = self._items.get(export_id)
            if stored_export is None or stored_export.expires_at < now:
                self._items.pop(export_id, None)
                return None
            return stored_export

    def _purge_expired_locked(self, *, now: datetime) -> None:
        expired_ids = [export_id for export_id, item in self._items.items() if item.expires_at < now]
        for export_id in expired_ids:
            self._items.pop(export_id, None)


def _build_export_file_name(chat_name: str, chat_id: int) -> str:
    normalized_name = re.sub(r"[^A-Za-z0-9._-]+", "-", chat_name.strip()).strip("-").lower()
    if not normalized_name:
        normalized_name = f"chat-{chat_id}"
    return f"{normalized_name[:80]}-{chat_id}.json"
