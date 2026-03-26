from __future__ import annotations

import logging
from typing import Any, cast

from aiohttp import web
from telethon import TelegramClient

from ..infrastructure.config import Settings
from ..infrastructure.in_memory_chat_export_store import InMemoryChatExportStore
from ..infrastructure.media_proxy import parse_proxy_export_token, parse_proxy_media_token
from ..infrastructure.telethon_helpers import extract_message_media

logger = logging.getLogger(__name__)


class MediaProxyServer:
    def __init__(
        self,
        client: TelegramClient,
        settings: Settings,
        export_store: InMemoryChatExportStore,
    ) -> None:
        self._client = client
        self._settings = settings
        self._export_store = export_store
        self._runner: web.AppRunner | None = None
        self._site: web.BaseSite | None = None
        self._app = web.Application()
        self._app.router.add_get("/media/{token}", self._download_media)
        self._app.router.add_get("/exports/{token}", self._download_export)

    async def start(self) -> None:
        if self._runner is not None:
            return
        self._runner = web.AppRunner(self._app, max_field_size=16384)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner,
            host=self._settings.media_proxy_host,
            port=self._settings.media_proxy_port,
        )
        await self._site.start()
        logger.info("Media proxy available on %s", self._settings.media_proxy_public_base_url)

    async def stop(self) -> None:
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def _download_media(self, request: web.Request) -> web.StreamResponse:
        token = request.match_info.get("token", "")
        try:
            target = parse_proxy_media_token(
                token,
                secret=self._settings.media_proxy_token_secret,
            )
        except ValueError as exc:
            if "expired" in str(exc).casefold():
                raise web.HTTPGone(text="Media URL expired") from exc
            raise web.HTTPNotFound(text="Invalid media URL") from exc

        try:
            entity = await self._client.get_entity(target.chat_id)
            message = await self._client.get_messages(entity, ids=target.message_id)
            if message is None:
                raise web.HTTPNotFound(text="Message not found")

            media = extract_message_media(message)
            if media is None:
                raise web.HTTPNotFound(text="Message has no media")

            max_bytes = self._settings.media_download_limit_bytes
            if media.size_bytes is not None and media.size_bytes > max_bytes:
                return web.Response(
                    status=413,
                    text=f"Media exceeds size limit ({max_bytes} bytes)",
                )

            content = await self._client.download_media(message, file=cast(Any, bytes))
            if not isinstance(content, bytes):
                return web.Response(status=502, text="Failed to download media")
            if len(content) > max_bytes:
                return web.Response(
                    status=413,
                    text=f"Media exceeds size limit ({max_bytes} bytes)",
                )

            headers = {"Cache-Control": "private, max-age=300"}
            mime_type = media.mime_type or "application/octet-stream"
            headers["Content-Type"] = mime_type
            if media.file_name:
                headers["Content-Disposition"] = (
                    f'inline; filename="{_safe_header_filename(media.file_name)}"'
                )

            return web.Response(body=content, headers=headers)
        except web.HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - defensive provider mapping
            logger.exception(
                "Media proxy failed",
                extra={"chat_id": target.chat_id, "message_id": target.message_id},
            )
            return web.Response(status=502, text=f"Telegram provider error: {exc}")

    async def _download_export(self, request: web.Request) -> web.StreamResponse:
        token = request.match_info.get("token", "")
        try:
            target = parse_proxy_export_token(
                token,
                secret=self._settings.media_proxy_token_secret,
            )
        except ValueError as exc:
            if "expired" in str(exc).casefold():
                raise web.HTTPGone(text="Export URL expired") from exc
            raise web.HTTPNotFound(text="Invalid export URL") from exc

        stored_export = await self._export_store.get_export(target.export_id)
        if stored_export is None:
            raise web.HTTPNotFound(text="Export file not found")

        headers = {
            "Cache-Control": "private, max-age=300",
            "Content-Type": stored_export.mime_type,
            "Content-Disposition": f'attachment; filename="{_safe_header_filename(stored_export.file_name)}"',
        }
        return web.Response(body=stored_export.content, headers=headers)


def _safe_header_filename(file_name: str) -> str:
    return file_name.replace("\\", "_").replace('"', "_").replace("\r", "").replace("\n", "")
