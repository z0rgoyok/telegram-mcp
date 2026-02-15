from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from mcp.server.fastmcp import FastMCP

from ..infrastructure.config import Settings
from ..infrastructure.telethon_adapter import TelethonAdapter
from . import tools


def create_server() -> FastMCP:
    settings = Settings.from_env()
    adapter = TelethonAdapter(settings)

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[None]:
        await adapter.connect()
        try:
            yield
        finally:
            await adapter.disconnect()

    mcp = FastMCP(
        "Telegram (read-only)",
        lifespan=lifespan,
    )

    @mcp.tool()
    async def list_chats(limit: int = 50, filter: str = "all") -> str:
        """List your Telegram chats, channels, and groups.

        Args:
            limit: Number of chats to return (1-200, default 50).
            filter: Filter by type: "all", "channels", "groups", "users".
        """
        return await tools.list_chats(adapter, limit=limit, filter=filter)

    @mcp.tool()
    async def get_messages(
        chat_id: int | str = 0,
        limit: int = 50,
        offset_date: str | None = None,
        search: str | None = None,
    ) -> str:
        """Get messages from a Telegram chat.

        Args:
            chat_id: Chat ID (number) or @username.
            limit: Number of messages (1-200, default 50).
            offset_date: Only messages before this date (ISO format, e.g. "2025-01-15").
            search: Filter messages containing this text.
        """
        return await tools.get_messages(
            adapter, chat_id=chat_id, limit=limit,
            offset_date=offset_date, search=search,
        )

    @mcp.tool()
    async def search_messages(
        query: str = "",
        chat_id: int | str | None = None,
        limit: int = 20,
    ) -> str:
        """Search messages globally or in a specific chat.

        Args:
            query: Search text (required).
            chat_id: Optional chat ID or @username to limit search.
            limit: Number of results (1-100, default 20).
        """
        return await tools.search_messages(
            adapter, query=query, chat_id=chat_id, limit=limit,
        )

    return mcp
