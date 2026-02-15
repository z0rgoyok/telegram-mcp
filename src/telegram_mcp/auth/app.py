from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from pathlib import Path
from typing import cast

from aiohttp import web
from telethon import TelegramClient

from ..infrastructure.config import Settings
from .handlers import AuthHandlers

STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger(__name__)


def create_auth_app(settings: Settings) -> web.Application:
    client = TelegramClient(
        str(settings.session_path),
        settings.api_id,
        settings.api_hash,
    )
    handlers = AuthHandlers(client, settings.phone)

    app = web.Application()
    app["client"] = client

    app.router.add_get("/api/status", handlers.status)
    app.router.add_post("/api/send-code", handlers.send_code)
    app.router.add_post("/api/sign-in", handlers.sign_in)
    app.router.add_post("/api/verify-2fa", handlers.verify_2fa)
    app.router.add_get("/", _serve_index)
    app.router.add_static("/static", STATIC_DIR)

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    return app


async def _serve_index(_request: web.Request) -> web.StreamResponse:
    index_path = STATIC_DIR / "index.html"
    return web.FileResponse(index_path)


async def _on_startup(app: web.Application) -> None:
    client: TelegramClient = app["client"]
    await client.connect()
    logger.info("Auth service: Telethon connected")


async def _on_cleanup(app: web.Application) -> None:
    client: TelegramClient = app["client"]
    await _maybe_await(client.disconnect())
    logger.info("Auth service: Telethon disconnected")


def run_auth_server() -> None:
    settings = Settings.from_env()
    app = create_auth_app(settings)

    async def _run() -> None:
        runner = web.AppRunner(app, max_field_size=16384)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=8901)

        await site.start()
        logger.info("Auth UI: http://0.0.0.0:8901")
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Auth service stopped by user")


async def _maybe_await(value: object) -> None:
    if hasattr(value, "__await__"):
        await cast(Awaitable[object], value)
