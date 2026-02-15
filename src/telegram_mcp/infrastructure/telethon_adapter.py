from __future__ import annotations

import logging

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError

from ..domain.errors import ErrorCode, ToolError
from ..domain.models import (
    AuthStatus,
    ChatActivity,
    ChatActivitySummary,
    ChatFilter,
    ChatMessagesBatchItem,
    ChatRef,
    ChatSnapshot,
    HealthStatus,
    MediaFile,
    MediaKind,
    MentionChatActivity,
    MessageContext,
    MessageInfo,
    MessageOrder,
    Page,
    ThreadMessages,
    TimeRange,
)
from ..domain.ports import TelegramReader
from .config import Settings
from .telethon_chat_ops import list_dialogs as list_dialogs_op
from .telethon_chat_ops import list_unread_dialogs as list_unread_dialogs_op
from .telethon_chat_ops import resolve_chat as resolve_chat_op
from .telethon_helpers import maybe_await
from .telethon_message_ops import (
    get_chat_snapshot as get_chat_snapshot_op,
)
from .telethon_message_ops import (
    get_message_context as get_message_context_op,
)
from .telethon_message_ops import (
    get_message_media as get_message_media_op,
)
from .telethon_message_ops import (
    get_messages as get_messages_op,
)
from .telethon_message_ops import (
    get_messages_batch as get_messages_batch_op,
)
from .telethon_message_ops import (
    get_thread_messages as get_thread_messages_op,
)
from .telethon_message_ops import (
    list_chat_activity_summary as list_chat_activity_summary_op,
)
from .telethon_message_ops import (
    list_media_messages as list_media_messages_op,
)
from .telethon_message_ops import (
    list_mentions_to_me_chats as list_mentions_to_me_chats_op,
)
from .telethon_message_ops import (
    list_my_sent_chats as list_my_sent_chats_op,
)
from .telethon_message_ops import (
    list_replies_to_me as list_replies_to_me_op,
)
from .telethon_message_ops import (
    search_mentions_to_me as search_mentions_to_me_op,
)
from .telethon_message_ops import (
    search_messages as search_messages_op,
)

logger = logging.getLogger(__name__)


class TelethonAdapter(TelegramReader):
    """TelegramReader implementation backed by Telethon."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = TelegramClient(
            str(settings.session_path),
            settings.api_id,
            settings.api_hash,
            flood_sleep_threshold=30,
        )

    @property
    def raw_client(self) -> TelegramClient:
        return self._client

    async def connect(self) -> None:
        try:
            await self._client.connect()
            if not await self._client.is_user_authorized():
                raise ToolError(
                    ErrorCode.UNAUTHORIZED,
                    "Telegram session not authorized",
                    {
                        "hint": (
                            "Run the auth service first: "
                            "docker compose --profile auth run --rm --service-ports auth"
                        )
                    },
                )
            me = await self._client.get_me()
            me_payload = me
            first_name = me_payload.first_name if hasattr(me_payload, "first_name") else None
            display_name = first_name if isinstance(first_name, str) and first_name else "user"
            user_id = me_payload.id if hasattr(me_payload, "id") else "unknown"
            logger.info("Connected as %s (id=%s)", display_name, user_id)
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def disconnect(self) -> None:
        await maybe_await(self._client.disconnect())

    async def list_dialogs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        chat_filter: ChatFilter = ChatFilter.ALL,
        query: str | None = None,
        unread_only: bool = False,
    ) -> Page[ChatRef]:
        try:
            return await list_dialogs_op(
                self._client,
                dialog_scan_limit=self._settings.dialog_scan_limit,
                limit=limit,
                offset=offset,
                chat_filter=chat_filter,
                query=query,
                unread_only=unread_only,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def list_unread_dialogs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[ChatRef]:
        try:
            return await list_unread_dialogs_op(
                self._client,
                dialog_scan_limit=self._settings.dialog_scan_limit,
                limit=limit,
                offset=offset,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def resolve_chat(
        self,
        *,
        query: str,
        limit: int = 20,
    ) -> list[ChatRef]:
        try:
            return await resolve_chat_op(
                self._client,
                dialog_scan_limit=self._settings.dialog_scan_limit,
                query=query,
                limit=limit,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def list_my_sent_chats(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        time_range: TimeRange,
    ) -> Page[ChatActivity]:
        try:
            return await list_my_sent_chats_op(
                self._client,
                limit=limit,
                offset=offset,
                time_range=time_range,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def list_mentions_to_me_chats(
        self,
        *,
        mention: str,
        limit: int = 50,
        offset: int = 0,
        time_range: TimeRange | None = None,
    ) -> Page[MentionChatActivity]:
        try:
            return await list_mentions_to_me_chats_op(
                self._client,
                mention=mention,
                limit=limit,
                offset=offset,
                time_range=time_range,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

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
        try:
            return await get_messages_op(
                self._client,
                chat_id=chat_id,
                limit=limit,
                offset_id=offset_id,
                time_range=time_range,
                order=order,
                search=search,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def get_message_context(
        self,
        *,
        chat_id: int | str,
        message_id: int,
        before: int,
        after: int,
    ) -> MessageContext:
        try:
            return await get_message_context_op(
                self._client,
                chat_id=chat_id,
                message_id=message_id,
                before=before,
                after=after,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def get_thread_messages(
        self,
        *,
        chat_id: int | str,
        root_message_id: int,
        limit: int = 50,
        offset_id: int | None = None,
    ) -> ThreadMessages:
        try:
            return await get_thread_messages_op(
                self._client,
                chat_id=chat_id,
                root_message_id=root_message_id,
                limit=limit,
                offset_id=offset_id,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

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
        try:
            return await search_messages_op(
                self._client,
                query=query,
                chat_id=chat_id,
                sender_query=sender_query,
                limit=limit,
                offset_id=offset_id,
                time_range=time_range,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def search_mentions_to_me(
        self,
        *,
        mention: str,
        chat_id: int | str | None = None,
        limit: int = 20,
        offset_id: int | None = None,
        time_range: TimeRange | None = None,
    ) -> Page[MessageInfo]:
        try:
            return await search_mentions_to_me_op(
                self._client,
                mention=mention,
                chat_id=chat_id,
                limit=limit,
                offset_id=offset_id,
                time_range=time_range,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def list_replies_to_me(
        self,
        *,
        chat_id: int | str | None = None,
        limit: int = 20,
        offset_id: int | None = None,
        time_range: TimeRange | None = None,
    ) -> Page[MessageInfo]:
        try:
            return await list_replies_to_me_op(
                self._client,
                chat_id=chat_id,
                limit=limit,
                offset_id=offset_id,
                time_range=time_range,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def get_messages_batch(
        self,
        *,
        chat_ids: list[int | str],
        limit_per_chat: int = 20,
        time_range: TimeRange | None = None,
        order: MessageOrder = MessageOrder.DESC,
        search: str | None = None,
    ) -> list[ChatMessagesBatchItem]:
        try:
            return await get_messages_batch_op(
                self._client,
                chat_ids=chat_ids,
                limit_per_chat=limit_per_chat,
                time_range=time_range,
                order=order,
                search=search,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def list_media_messages(
        self,
        *,
        chat_id: int | str | None = None,
        media_kind: MediaKind | None = None,
        limit: int = 20,
        offset_id: int | None = None,
        time_range: TimeRange | None = None,
    ) -> Page[MessageInfo]:
        try:
            return await list_media_messages_op(
                self._client,
                chat_id=chat_id,
                media_kind=media_kind,
                limit=limit,
                offset_id=offset_id,
                time_range=time_range,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def list_chat_activity_summary(
        self,
        *,
        mention: str,
        limit: int = 50,
        offset: int = 0,
        time_range: TimeRange,
    ) -> Page[ChatActivitySummary]:
        try:
            return await list_chat_activity_summary_op(
                self._client,
                dialog_scan_limit=self._settings.dialog_scan_limit,
                mention=mention,
                limit=limit,
                offset=offset,
                time_range=time_range,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def get_chat_snapshot(
        self,
        *,
        chat_id: int | str,
        recent_limit: int,
        include_pinned: bool,
    ) -> ChatSnapshot:
        try:
            return await get_chat_snapshot_op(
                self._client,
                dialog_scan_limit=self._settings.dialog_scan_limit,
                chat_id=chat_id,
                recent_limit=recent_limit,
                include_pinned=include_pinned,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def get_message_media(
        self,
        *,
        chat_id: int | str,
        message_id: int,
    ) -> MediaFile:
        try:
            return await get_message_media_op(
                self._client,
                chat_id=chat_id,
                message_id=message_id,
                max_bytes=self._settings.media_download_limit_bytes,
                proxy_public_base_url=self._settings.media_proxy_public_base_url,
                proxy_token_secret=self._settings.media_proxy_token_secret,
                proxy_token_ttl_seconds=self._settings.media_proxy_token_ttl_seconds,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def get_auth_status(self) -> AuthStatus:
        try:
            connected = self._client.is_connected()
            authorized = await self._client.is_user_authorized()
            if not authorized:
                return AuthStatus(connected=connected, authorized=False)

            me = await self._client.get_me()
            me_payload = me
            first_name_obj = me_payload.first_name if hasattr(me_payload, "first_name") else None
            last_name_obj = me_payload.last_name if hasattr(me_payload, "last_name") else None
            first_name = first_name_obj if isinstance(first_name_obj, str) else ""
            last_name = last_name_obj if isinstance(last_name_obj, str) else ""
            name_parts = [first_name, last_name]
            full_name = " ".join(part for part in name_parts if part).strip() or None
            user_id_obj = me_payload.id if hasattr(me_payload, "id") else None
            username_obj = me_payload.username if hasattr(me_payload, "username") else None
            return AuthStatus(
                connected=connected,
                authorized=True,
                user_id=user_id_obj if isinstance(user_id_obj, int) else None,
                name=full_name,
                username=username_obj if isinstance(username_obj, str) else None,
            )
        except Exception as exc:
            raise self._map_error(exc) from exc

    async def health_check(self) -> HealthStatus:
        try:
            connected = self._client.is_connected()
            authorized = await self._client.is_user_authorized() if connected else False
            status = "ok" if connected and authorized else "degraded"
            return HealthStatus(status=status, connected=connected, authorized=authorized)
        except Exception as exc:
            raise self._map_error(exc) from exc

    @staticmethod
    def _map_error(exc: Exception) -> ToolError:
        if isinstance(exc, ToolError):
            return exc

        if isinstance(exc, FloodWaitError):
            retry_after_obj = exc.seconds if hasattr(exc, "seconds") else None
            return ToolError(
                ErrorCode.RATE_LIMITED,
                "Telegram rate limit exceeded",
                {"retry_after_seconds": retry_after_obj if isinstance(retry_after_obj, int) else None},
            )

        if isinstance(exc, ValueError):
            return ToolError(
                ErrorCode.NOT_FOUND,
                "Telegram entity not found",
                {"error": str(exc)},
            )

        class_name = exc.__class__.__name__
        if class_name in {
            "UnauthorizedError",
            "AuthKeyUnregisteredError",
            "SessionRevokedError",
            "SessionExpiredError",
            "AuthKeyError",
            "UserDeactivatedError",
        }:
            return ToolError(ErrorCode.UNAUTHORIZED, "Telegram session is not authorized")

        if isinstance(exc, RPCError):
            return ToolError(
                ErrorCode.PROVIDER_ERROR,
                "Telegram provider error",
                {"error_type": class_name, "error": str(exc)},
            )

        return ToolError(
            ErrorCode.PROVIDER_ERROR,
            "Unexpected Telegram provider error",
            {"error_type": class_name, "error": str(exc)},
        )
