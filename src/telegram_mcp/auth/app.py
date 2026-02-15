from __future__ import annotations

import sys
from pathlib import Path

from aiohttp import web
from telethon import TelegramClient

from ..infrastructure.config import Settings
from .handlers import AuthHandlers

STATIC_DIR = Path(__file__).parent / "static"


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


async def _serve_index(_request: web.Request) -> web.Response:
    index_path = STATIC_DIR / "index.html"
    return web.FileResponse(index_path)


async def _on_startup(app: web.Application) -> None:
    client: TelegramClient = app["client"]
    await client.connect()
    print("Auth service: Telethon connected", file=sys.stderr)


async def _on_cleanup(app: web.Application) -> None:
    client: TelegramClient = app["client"]
    await client.disconnect()
    print("Auth service: Telethon disconnected", file=sys.stderr)


def run_auth_server() -> None:
    settings = Settings.from_env()
    app = create_auth_app(settings)
    print("Auth UI: http://0.0.0.0:8901", file=sys.stderr)
    web.run_app(app, host="0.0.0.0", port=8901, print=None)
