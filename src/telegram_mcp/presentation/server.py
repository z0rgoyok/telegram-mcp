from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..application.executor import execute_use_case
from ..application.responses import error_response
from ..application.use_cases import TelegramUseCases
from ..domain.errors import ErrorCode, ToolError
from ..domain.ports import TelegramReader
from ..infrastructure.config import Settings
from ..infrastructure.telethon_adapter import TelethonAdapter
from .formatters import format_markdown
from .media_proxy_server import MediaProxyServer

logger = logging.getLogger(__name__)


def create_server() -> FastMCP:
    settings = Settings.from_env()
    adapter_impl = TelethonAdapter(settings)
    media_proxy = MediaProxyServer(adapter_impl.raw_client, settings)
    reader: TelegramReader = adapter_impl
    use_cases = TelegramUseCases(reader)

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[None]:
        await adapter_impl.connect()
        try:
            await media_proxy.start()
            try:
                yield
            finally:
                await media_proxy.stop()
        finally:
            await adapter_impl.disconnect()

    mcp = FastMCP(
        "Telegram (read-only)",
        lifespan=lifespan,
    )

    @mcp.tool()
    async def resolve_chat(
        query: str,
        limit: int = 20,
        response_format: str = "json",
    ) -> dict[str, Any] | str:
        payload = await execute_use_case(use_cases.resolve_chat, query=query, limit=limit)
        return _render_response("resolve_chat", payload, response_format)

    @mcp.tool()
    async def list_chats(
        chat_filter: str = "all",
        query: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
        cursor: str | None = None,
        response_format: str = "json",
    ) -> dict[str, Any] | str:
        payload = await execute_use_case(
            use_cases.list_chats,
            chat_filter=chat_filter,
            query=query,
            unread_only=unread_only,
            limit=limit,
            cursor=cursor,
        )
        return _render_response("list_chats", payload, response_format)

    @mcp.tool()
    async def list_unread_chats(
        limit: int = 50,
        cursor: str | None = None,
        response_format: str = "json",
    ) -> dict[str, Any] | str:
        payload = await execute_use_case(
            use_cases.list_unread_chats,
            limit=limit,
            cursor=cursor,
        )
        return _render_response("list_unread_chats", payload, response_format)

    @mcp.tool()
    async def get_messages(
        chat_id: int | str,
        limit: int = 50,
        cursor: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        order: str = "desc",
        search: str | None = None,
        response_format: str = "json",
    ) -> dict[str, Any] | str:
        payload = await execute_use_case(
            use_cases.get_messages,
            chat_id=chat_id,
            limit=limit,
            cursor=cursor,
            from_date=from_date,
            to_date=to_date,
            order=order,
            search=search,
        )
        return _render_response("get_messages", payload, response_format)

    @mcp.tool()
    async def get_message_context(
        chat_id: int | str,
        message_id: int,
        before: int = 20,
        after: int = 20,
        response_format: str = "json",
    ) -> dict[str, Any] | str:
        payload = await execute_use_case(
            use_cases.get_message_context,
            chat_id=chat_id,
            message_id=message_id,
            before=before,
            after=after,
        )
        return _render_response("get_message_context", payload, response_format)

    @mcp.tool()
    async def get_thread_messages(
        chat_id: int | str,
        root_message_id: int,
        limit: int = 50,
        cursor: str | None = None,
        response_format: str = "json",
    ) -> dict[str, Any] | str:
        payload = await execute_use_case(
            use_cases.get_thread_messages,
            chat_id=chat_id,
            root_message_id=root_message_id,
            limit=limit,
            cursor=cursor,
        )
        return _render_response("get_thread_messages", payload, response_format)

    @mcp.tool()
    async def search_messages(
        query: str,
        chat_id: int | str | None = None,
        sender_query: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
        response_format: str = "json",
    ) -> dict[str, Any] | str:
        payload = await execute_use_case(
            use_cases.search_messages,
            query=query,
            chat_id=chat_id,
            sender_query=sender_query,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            cursor=cursor,
        )
        return _render_response("search_messages", payload, response_format)

    @mcp.tool()
    async def get_chat_snapshot(
        chat_id: int | str,
        recent_limit: int = 20,
        include_pinned: bool = True,
        response_format: str = "json",
    ) -> dict[str, Any] | str:
        payload = await execute_use_case(
            use_cases.get_chat_snapshot,
            chat_id=chat_id,
            recent_limit=recent_limit,
            include_pinned=include_pinned,
        )
        return _render_response("get_chat_snapshot", payload, response_format)

    @mcp.tool()
    async def get_message_media(
        chat_id: int | str,
        message_id: int,
        response_format: str = "json",
    ) -> dict[str, Any] | str:
        payload = await execute_use_case(
            use_cases.get_message_media,
            chat_id=chat_id,
            message_id=message_id,
        )
        return _render_response("get_message_media", payload, response_format)

    @mcp.tool()
    async def get_auth_status(response_format: str = "json") -> dict[str, Any] | str:
        payload = await execute_use_case(use_cases.get_auth_status)
        return _render_response("get_auth_status", payload, response_format)

    @mcp.tool()
    async def health_check(response_format: str = "json") -> dict[str, Any] | str:
        payload = await execute_use_case(use_cases.health_check)
        return _render_response("health_check", payload, response_format)

    return mcp


def _render_response(tool_name: str, payload: dict[str, Any], response_format: str) -> dict[str, Any] | str:
    if response_format == "json":
        return payload
    if response_format == "markdown":
        return format_markdown(tool_name, payload)

    invalid = error_response(
        ToolError(
            ErrorCode.VALIDATION_ERROR,
            "Unsupported format",
            {"allowed": ["json", "markdown"], "value": response_format},
        )
    )
    return invalid
