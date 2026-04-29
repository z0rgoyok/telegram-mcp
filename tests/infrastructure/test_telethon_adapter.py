from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from telethon import functions, types

from tests.conftest import load_attr

ErrorCode = load_attr("telegram_mcp.domain.errors", "ErrorCode")
MediaKind = load_attr("telegram_mcp.domain.models", "MediaKind")
MessageOrder = load_attr("telegram_mcp.domain.models", "MessageOrder")
TimeRange = load_attr("telegram_mcp.domain.models", "TimeRange")
Settings = load_attr("telegram_mcp.infrastructure.config", "Settings")
TelethonAdapter = load_attr("telegram_mcp.infrastructure.telethon_adapter", "TelethonAdapter")
ToolError = load_attr("telegram_mcp.domain.errors", "ToolError")


def make_group(chat_id: int, title: str) -> types.Chat:
    return types.Chat(
        id=chat_id,
        title=title,
        photo=types.ChatPhotoEmpty(),
        participants_count=10,
        date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        version=0,
    )


def make_channel(channel_id: int, title: str, username: str | None = None) -> types.Channel:
    return types.Channel(
        id=channel_id,
        title=title,
        photo=types.ChatPhotoEmpty(),
        date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        broadcast=True,
        megagroup=False,
        access_hash=0,
        username=username,
    )


@dataclass
class FakeReply:
    reply_to_msg_id: int


@dataclass
class FakeFile:
    name: str
    mime_type: str
    size: int
    url: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None


@dataclass
class FakeMessage:
    id: int
    date: datetime
    text: str
    chat_id: int
    sender_id: int | None
    sender: object | None
    chat: object | None
    reply_to: FakeReply | None = None
    pinned: bool = False
    media: object | None = None
    file: FakeFile | None = None
    photo: object | None = None
    video: object | None = None
    voice: object | None = None
    audio: object | None = None
    sticker: object | None = None
    gif: object | None = None
    document: object | None = None
    reactions: object | None = None


@dataclass
class FakeDialog:
    id: int
    name: str
    entity: object
    unread_count: int
    date: datetime
    folder_id: int | None = None


class FakeClient:
    def __init__(self) -> None:
        self._connected = True
        self._authorized = True
        self.leave_channel_requests: list[int] = []
        self.deleted_dialogs: list[int] = []
        self.iterated_message_ids: list[int] = []

        self.entities = {
            1: SimpleNamespace(id=1, title="Engineering", username="eng"),
            2: SimpleNamespace(id=2, title="Support", username="support"),
            3: SimpleNamespace(id=3, title="Random", username="random"),
            10: make_group(10, "Engineering"),
            1275692770: make_channel(1275692770, "Android Group"),
        }

        self.dialogs = [
            FakeDialog(
                id=1,
                name="Engineering",
                entity=self.entities[1],
                unread_count=5,
                date=datetime(2026, 1, 3, 9, 0, tzinfo=timezone.utc),
                folder_id=1,
            ),
            FakeDialog(
                id=2,
                name="Support",
                entity=self.entities[2],
                unread_count=5,
                date=datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc),
                folder_id=0,
            ),
            FakeDialog(
                id=3,
                name="Random",
                entity=self.entities[3],
                unread_count=2,
                date=datetime(2026, 1, 4, 9, 0, tzinfo=timezone.utc),
                folder_id=None,
            ),
        ]

        user_alice = SimpleNamespace(id=100, first_name="Alice", last_name="A")
        user_bob = SimpleNamespace(id=200, first_name="Bob", last_name="B")

        self.messages: dict[int, list[FakeMessage]] = {
            1: [
                FakeMessage(14, datetime(2026, 1, 4, 10, 0, tzinfo=timezone.utc), "task update", 1, 200, user_bob, self.entities[1]),
                FakeMessage(15, datetime(2026, 1, 4, 9, 0, tzinfo=timezone.utc), "please check @tester later", 1, 200, user_bob, self.entities[1]),
                FakeMessage(13, datetime(2026, 1, 3, 10, 0, tzinfo=timezone.utc), "task started", 1, 100, user_alice, self.entities[1]),
                FakeMessage(12, datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc), "middle", 1, 100, user_alice, self.entities[1]),
                FakeMessage(11, datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc), "older", 1, 200, user_bob, self.entities[1]),
                FakeMessage(10, datetime(2025, 12, 31, 10, 0, tzinfo=timezone.utc), "oldest", 1, 100, user_alice, self.entities[1]),
                FakeMessage(20, datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc), "thread root", 1, 100, user_alice, self.entities[1], pinned=True),
                FakeMessage(22, datetime(2026, 1, 5, 10, 2, tzinfo=timezone.utc), "thread reply 2", 1, 100, user_alice, self.entities[1], reply_to=FakeReply(20)),
                FakeMessage(21, datetime(2026, 1, 5, 10, 1, tzinfo=timezone.utc), "thread reply 1", 1, 200, user_bob, self.entities[1], reply_to=FakeReply(20)),
                FakeMessage(
                    23,
                    datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc),
                    "",
                    1,
                    100,
                    user_alice,
                    self.entities[1],
                    media=SimpleNamespace(spoiler=False),
                    file=FakeFile(
                        name="photo.jpg",
                        mime_type="image/jpeg",
                        size=4,
                        width=640,
                        height=480,
                    ),
                    photo=SimpleNamespace(id=7001),
                ),
            ],
            2: [
                FakeMessage(31, datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc), "support task", 2, 200, user_bob, self.entities[2]),
            ],
            3: [],
        }

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def is_user_authorized(self) -> bool:
        return self._authorized

    def is_connected(self) -> bool:
        return self._connected

    async def get_me(self) -> object:
        _ = self._authorized
        return SimpleNamespace(id=100, first_name="Tester", last_name="User", username="tester")

    async def get_entity(self, chat_id: int | str) -> object:
        if hasattr(chat_id, "channel_id") and isinstance(chat_id.channel_id, int):
            if chat_id.channel_id in self.entities:
                return self.entities[chat_id.channel_id]
            raise ValueError("Entity not found")
        if hasattr(chat_id, "chat_id") and isinstance(chat_id.chat_id, int):
            if chat_id.chat_id in self.entities:
                return self.entities[chat_id.chat_id]
            raise ValueError("Entity not found")
        if hasattr(chat_id, "user_id") and isinstance(chat_id.user_id, int):
            if chat_id.user_id in self.entities:
                return self.entities[chat_id.user_id]
            raise ValueError("Entity not found")

        if isinstance(chat_id, str):
            key = chat_id.strip()
            if key.startswith("@"):
                key = key[1:]
            for entity in self.entities.values():
                if getattr(entity, "username", None) == key:
                    return entity
            if key.lstrip("-").isdigit():
                value = int(key)
                if value in self.entities:
                    return self.entities[value]
            raise ValueError("Entity not found")

        if chat_id in self.entities:
            return self.entities[chat_id]
        raise ValueError("Entity not found")

    @staticmethod
    async def get_input_entity(entity: Any) -> Any:
        if isinstance(entity, types.Channel):
            return types.InputPeerChannel(channel_id=entity.id, access_hash=entity.access_hash or 0)
        if isinstance(entity, types.Chat):
            return types.InputPeerChat(chat_id=entity.id)
        if isinstance(entity, types.User):
            return types.InputPeerUser(user_id=entity.id, access_hash=entity.access_hash or 0)
        if hasattr(entity, "id") and isinstance(entity.id, int):
            return types.InputPeerUser(user_id=entity.id, access_hash=0)
        raise ValueError("Entity not found")

    async def delete_dialog(self, entity: Any, *, revoke: bool = False) -> None:
        _ = revoke
        if not hasattr(entity, "id") or not isinstance(entity.id, int):
            raise ValueError("Entity not found")
        self.deleted_dialogs.append(entity.id)

    async def get_messages(self, entity: Any, ids: int | list[int]) -> FakeMessage | list[FakeMessage] | None:
        chat_id = entity.id
        pool = self.messages.get(chat_id, [])
        if isinstance(ids, list):
            requested = set(ids)
            return [message for message in pool if message.id in requested]

        for message in pool:
            if message.id == ids:
                return message
        return None

    async def iter_dialogs(self, limit: int, folder: int | None = None) -> Any:
        dialogs = self.dialogs
        if folder is not None:
            dialogs = [dialog for dialog in dialogs if dialog.folder_id == folder]
        for dialog in dialogs[:limit]:
            yield dialog

    async def iter_messages(self, entity: Any | None, **kwargs: Any) -> Any:
        if entity is None:
            pool = [message for values in self.messages.values() for message in values]
        else:
            pool = list(self.messages.get(entity.id, []))

        search = kwargs.get("search")
        if search:
            text = str(search).casefold()
            pool = [item for item in pool if text in item.text.casefold()]

        reply_to = kwargs.get("reply_to")
        if reply_to is not None:
            pool = [
                item
                for item in pool
                if item.reply_to is not None and item.reply_to.reply_to_msg_id == int(reply_to)
            ]

        message_filter = kwargs.get("filter")
        if message_filter is not None:
            pool = [item for item in pool if item.pinned]

        offset_date = kwargs.get("offset_date")
        if isinstance(offset_date, datetime):
            pool = [item for item in pool if item.date <= offset_date]

        offset_id = kwargs.get("offset_id")
        if isinstance(offset_id, int):
            pool = [item for item in pool if item.id < offset_id]

        min_id = kwargs.get("min_id")
        if isinstance(min_id, int):
            pool = [item for item in pool if item.id > min_id]

        reverse = bool(kwargs.get("reverse", False))
        pool.sort(key=lambda item: item.id, reverse=not reverse)

        limit = int(kwargs.get("limit", len(pool)))
        for message in pool[:limit]:
            self.iterated_message_ids.append(message.id)
            yield message

    async def __call__(self, request: Any) -> Any:
        if isinstance(request, functions.messages.GetDialogFiltersRequest):
            return SimpleNamespace(
                filters=[
                    types.DialogFilter(
                        id=139,
                        title=types.TextWithEntities(text="Fix Price", entities=[]),
                        pinned_peers=[],
                        include_peers=[
                            types.InputPeerChannel(channel_id=1275692770, access_hash=0),
                        ],
                        exclude_peers=[],
                        contacts=False,
                        non_contacts=False,
                        groups=False,
                        broadcasts=False,
                        bots=False,
                        exclude_muted=False,
                        exclude_read=False,
                        exclude_archived=False,
                        title_noanimate=False,
                        emoticon="",
                        color=0,
                    )
                ],
                tags_enabled=False,
            )
        if isinstance(request, functions.messages.SearchRequest):
            pool = [message for values in self.messages.values() for message in values]

            query = request.q if hasattr(request, "q") else None
            if isinstance(query, str) and query:
                normalized_query = query.casefold()
                pool = [message for message in pool if normalized_query in message.text.casefold()]

            from_user_id = request.from_id.user_id if hasattr(request.from_id, "user_id") else None
            if isinstance(from_user_id, int):
                pool = [message for message in pool if message.sender_id == from_user_id]

            if isinstance(request.max_date, datetime):
                pool = [message for message in pool if message.date <= request.max_date]
            if isinstance(request.min_date, datetime):
                pool = [message for message in pool if message.date >= request.min_date]
            if isinstance(request.offset_id, int) and request.offset_id > 0:
                pool = [message for message in pool if message.id < request.offset_id]

            pool.sort(key=lambda message: message.id, reverse=True)
            limit = int(request.limit) if isinstance(request.limit, int) and request.limit > 0 else len(pool)
            selected = pool[:limit]
            messages = [
                SimpleNamespace(
                    id=item.id,
                    date=item.date,
                    text=item.text,
                    peer_id=types.PeerUser(user_id=item.chat_id),
                    from_id=types.PeerUser(user_id=item.sender_id) if item.sender_id is not None else None,
                )
                for item in selected
            ]
            return SimpleNamespace(messages=messages, users=[], chats=list(self.entities.values()))
        if isinstance(request, functions.channels.LeaveChannelRequest):
            channel = request.channel
            if hasattr(channel, "channel_id") and isinstance(channel.channel_id, int):
                self.leave_channel_requests.append(channel.channel_id)
                return SimpleNamespace()

        raise AssertionError(f"Unsupported request type: {type(request).__name__}")

    async def download_media(self, message: Any, file: Any = None) -> bytes:
        _ = self
        _ = file
        if getattr(message, "id", None) == 23:
            return b"\x00\x01\x02\x03"
        return b""


@pytest.fixture
def adapter(tmp_path: Path) -> Any:
    settings = Settings(
        api_id=1,
        api_hash="hash",
        phone="+10000000000",
        session_path=tmp_path / "telegram-test",
        dialog_scan_limit=100,
        media_download_limit_bytes=1024,
        media_proxy_host="0.0.0.0",
        media_proxy_port=8902,
        media_proxy_public_base_url="http://proxy.test",
        media_proxy_token_secret="secret",
        media_proxy_token_ttl_seconds=3600,
    )
    instance = TelethonAdapter(settings)
    instance._client = FakeClient()
    return instance


@pytest.mark.asyncio
async def test_list_unread_dialogs_sorted_deterministically(adapter: Any) -> None:
    page = await adapter.list_unread_dialogs(limit=10, offset=0)

    assert [chat.id for chat in page.items] == [1, 2, 3]
    assert page.has_more is False


@pytest.mark.asyncio
async def test_list_dialogs_filters_by_folder(adapter: Any) -> None:
    page = await adapter.list_dialogs(limit=10, offset=0, folder=1)

    assert [chat.id for chat in page.items] == [1]
    assert page.has_more is False


@pytest.mark.asyncio
async def test_list_unread_dialogs_filters_by_folder(adapter: Any) -> None:
    page = await adapter.list_unread_dialogs(limit=10, offset=0, folder=0)

    assert [chat.id for chat in page.items] == [2]
    assert page.has_more is False


@pytest.mark.asyncio
async def test_resolve_chat_finds_chat_from_custom_dialog_filter(adapter: Any) -> None:
    chats = await adapter.resolve_chat(query="Android Group", limit=10)

    assert any(chat.name == "Android Group" for chat in chats)


@pytest.mark.asyncio
async def test_list_dialogs_can_list_custom_dialog_filter_contents(adapter: Any) -> None:
    page = await adapter.list_dialogs(limit=10, offset=0, dialog_filter="Fix Price")

    assert [chat.name for chat in page.items] == ["Android Group"]
    assert page.has_more is False


@pytest.mark.asyncio
async def test_list_dialog_filters_returns_available_filters(adapter: Any) -> None:
    items = await adapter.list_dialog_filters()

    assert items == [
        load_attr("telegram_mcp.domain.models", "DialogFilterInfo")(
            id=139,
            title="Fix Price",
            kind="filter",
            peer_count=1,
        )
    ]


@pytest.mark.asyncio
async def test_unsubscribe_from_channel_leaves_broadcast_channel(adapter: Any) -> None:
    result = await adapter.unsubscribe_from_channel(chat_id=1275692770)

    assert result.chat_id == 1275692770
    assert result.chat_name == "Android Group"
    assert result.chat_type.value == "channel"
    assert result.action.value == "unsubscribed"
    assert adapter._client.leave_channel_requests == [1275692770]


@pytest.mark.asyncio
async def test_unsubscribe_from_channel_rejects_group(adapter: Any) -> None:
    with pytest.raises(ToolError, match="not a channel"):
        await adapter.unsubscribe_from_channel(chat_id=1)


@pytest.mark.asyncio
async def test_leave_chat_deletes_group_dialog(adapter: Any) -> None:
    result = await adapter.leave_chat(chat_id=10)

    assert result.chat_id == 10
    assert result.chat_name == "Engineering"
    assert result.chat_type.value == "group"
    assert result.action.value == "left"
    assert adapter._client.deleted_dialogs == [10]


@pytest.mark.asyncio
async def test_leave_chat_rejects_channel(adapter: Any) -> None:
    with pytest.raises(ToolError, match="use unsubscribe_from_channel"):
        await adapter.leave_chat(chat_id=1275692770)


@pytest.mark.asyncio
async def test_get_messages_supports_pagination(adapter: Any) -> None:
    page = await adapter.get_messages(chat_id=1, limit=2)

    assert [message.id for message in page.items] == [23, 22]
    assert page.has_more is True
    assert page.next_offset == 22


@pytest.mark.asyncio
async def test_get_message_context_returns_ordered_neighbours(adapter: Any) -> None:
    context = await adapter.get_message_context(chat_id=1, message_id=12, before=2, after=2)

    assert [message.id for message in context.before] == [10, 11]
    assert context.target.id == 12
    assert [message.id for message in context.after] == [13, 14]


@pytest.mark.asyncio
async def test_get_thread_messages_returns_root_and_replies(adapter: Any) -> None:
    thread = await adapter.get_thread_messages(chat_id=1, root_message_id=20, limit=10)

    assert thread.root.id == 20
    assert [message.id for message in thread.page.items] == [22, 21]


@pytest.mark.asyncio
async def test_search_messages_filters_sender_and_time_range(adapter: Any) -> None:
    page = await adapter.search_messages(
        query="task",
        sender_query="bob",
        limit=10,
        time_range=TimeRange(
            from_date=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            to_date=datetime(2026, 1, 31, 0, 0, tzinfo=timezone.utc),
        ),
    )

    assert [message.id for message in page.items] == [31, 14]


@pytest.mark.asyncio
async def test_search_messages_accepts_empty_query_as_wildcard(adapter: Any) -> None:
    page = await adapter.search_messages(query=None, limit=3)

    assert [message.id for message in page.items] == [31, 23, 22]


@pytest.mark.asyncio
async def test_list_my_sent_chats_returns_aggregated_activity(adapter: Any) -> None:
    page = await adapter.list_my_sent_chats(
        limit=10,
        offset=0,
        time_range=TimeRange(
            from_date=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            to_date=datetime(2026, 1, 5, 23, 59, tzinfo=timezone.utc),
        ),
    )

    assert len(page.items) == 1
    assert page.items[0].chat_id == 1
    assert page.items[0].my_messages_count == 4


@pytest.mark.asyncio
async def test_search_mentions_to_me_finds_mentions_in_message_text(adapter: Any) -> None:
    page = await adapter.search_mentions_to_me(mention="@tester", limit=10)

    assert [message.id for message in page.items] == [15]


@pytest.mark.asyncio
async def test_list_mentions_to_me_chats_returns_aggregated_activity(adapter: Any) -> None:
    page = await adapter.list_mentions_to_me_chats(mention="@tester", limit=10, offset=0)

    assert len(page.items) == 1
    assert page.items[0].chat_id == 1
    assert page.items[0].mentions_count == 1


@pytest.mark.asyncio
async def test_list_replies_to_me_returns_messages_replied_to_my_posts(adapter: Any) -> None:
    page = await adapter.list_replies_to_me(chat_id=1, limit=10)

    assert [message.id for message in page.items] == [22, 21]


@pytest.mark.asyncio
async def test_get_messages_batch_returns_items_per_chat(adapter: Any) -> None:
    items = await adapter.get_messages_batch(chat_ids=[1, 2], limit_per_chat=2)

    assert [item.chat_id for item in items] == [1, 2]
    assert [message.id for message in items[0].messages] == [23, 22]
    assert [message.id for message in items[1].messages] == [31]


@pytest.mark.asyncio
async def test_list_media_messages_filters_by_kind(adapter: Any) -> None:
    page = await adapter.list_media_messages(media_kind=MediaKind.PHOTO, limit=10)

    assert [message.id for message in page.items] == [23]


@pytest.mark.asyncio
async def test_list_chat_activity_summary_combines_my_and_mention_activity(adapter: Any) -> None:
    page = await adapter.list_chat_activity_summary(
        mention="@tester",
        limit=10,
        offset=0,
        time_range=TimeRange(
            from_date=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            to_date=datetime(2026, 1, 31, 0, 0, tzinfo=timezone.utc),
        ),
    )

    assert len(page.items) == 1
    assert page.items[0].chat_id == 1
    assert page.items[0].my_messages_count == 5
    assert page.items[0].mentions_to_me_count == 1


def test_map_error_to_unauthorized_code(adapter: Any) -> None:
    class UnauthorizedError(Exception):
        pass

    mapped = adapter._map_error(UnauthorizedError("bad session"))

    assert mapped.code == ErrorCode.UNAUTHORIZED


def test_map_error_to_rate_limited_code(adapter: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeFloodWaitError(Exception):
        def __init__(self, seconds: int) -> None:
            super().__init__("wait")
            self.seconds = seconds

    monkeypatch.setattr(
        "telegram_mcp.infrastructure.telethon_adapter.FloodWaitError",
        FakeFloodWaitError,
    )

    mapped = adapter._map_error(FakeFloodWaitError(12))

    assert mapped.code == ErrorCode.RATE_LIMITED
    assert mapped.details == {"retry_after_seconds": 12}


@pytest.mark.asyncio
async def test_health_check_reports_ok(adapter: Any) -> None:
    status = await adapter.health_check()

    assert status.status == "ok"
    assert status.connected is True
    assert status.authorized is True


@pytest.mark.asyncio
async def test_get_messages_with_ascending_order(adapter: Any) -> None:
    page = await adapter.get_messages(chat_id=1, limit=3, order=MessageOrder.ASC)

    assert [message.id for message in page.items] == [21, 22, 23]


@pytest.mark.asyncio
async def test_get_messages_includes_media_metadata(adapter: Any) -> None:
    page = await adapter.get_messages(chat_id=1, limit=1)

    media = page.items[0].media
    assert media is not None
    assert media.kind.value == "photo"
    assert media.mime_type == "image/jpeg"
    assert media.file_name == "photo.jpg"
    assert media.size_bytes == 4


@pytest.mark.asyncio
async def test_get_messages_includes_reactions(adapter: Any) -> None:
    message = next(item for item in adapter._client.messages[1] if item.id == 14)
    message.reactions = types.MessageReactions(
        results=[
            types.ReactionCount(
                reaction=types.ReactionEmoji(emoticon="👍"),
                count=2,
                chosen_order=0,
            ),
            types.ReactionCount(
                reaction=types.ReactionCustomEmoji(document_id=777),
                count=1,
            ),
        ]
    )

    page = await adapter.get_messages(chat_id=1, limit=10)

    target = next(item for item in page.items if item.id == 14)
    assert target.reactions[0].kind.value == "emoji"
    assert target.reactions[0].emoji == "👍"
    assert target.reactions[0].count == 2
    assert target.reactions[0].chosen is True
    assert target.reactions[1].kind.value == "custom_emoji"
    assert target.reactions[1].custom_emoji_id == 777
    assert target.reactions[1].count == 1


@pytest.mark.asyncio
async def test_get_message_media_returns_content(adapter: Any) -> None:
    media_file = await adapter.get_message_media(chat_id=1, message_id=23)

    assert media_file.kind.value == "photo"
    assert media_file.size_bytes == 4
    assert media_file.url_source.value == "proxy"
    assert media_file.content_url.startswith("http://proxy.test/media/")


@pytest.mark.asyncio
async def test_get_message_media_prefers_direct_telegram_url(adapter: Any) -> None:
    media_message = next(message for message in adapter._client.messages[1] if message.id == 23)
    assert media_message.file is not None
    media_message.file.url = "https://cdn.telegram.org/file/23.jpg"

    media_file = await adapter.get_message_media(chat_id=1, message_id=23)

    assert media_file.url_source.value == "telegram"
    assert media_file.content_url == "https://cdn.telegram.org/file/23.jpg"


@pytest.mark.asyncio
async def test_export_chat_returns_full_chat_with_media_urls(adapter: Any) -> None:
    chat_export = await adapter.export_chat(chat_id=1, include_media=True)

    assert chat_export.chat.id == 1
    assert chat_export.messages[0].message.id == 10
    assert chat_export.messages[-1].message.id == 23
    assert chat_export.messages[-1].media_file is not None
    assert chat_export.messages[-1].media_file.content_url.startswith("http://proxy.test/media/")


@pytest.mark.asyncio
async def test_export_chat_stops_scanning_after_from_date(adapter: Any) -> None:
    chat_export = await adapter.export_chat(
        chat_id=1,
        time_range=TimeRange(
            from_date=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
            to_date=datetime(2026, 1, 4, 23, 59, tzinfo=timezone.utc),
        ),
        include_media=False,
        order=MessageOrder.ASC,
    )

    assert [item.message.id for item in chat_export.messages] == [12, 13, 14, 15]
    assert adapter._client.iterated_message_ids == [15, 14, 13, 12, 11]
