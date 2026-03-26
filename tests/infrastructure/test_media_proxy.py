from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

import pytest

from tests.conftest import load_attr

build_proxy_media_url = load_attr("telegram_mcp.infrastructure.media_proxy", "build_proxy_media_url")
build_proxy_export_url = load_attr("telegram_mcp.infrastructure.media_proxy", "build_proxy_export_url")
extract_direct_media_url = load_attr("telegram_mcp.infrastructure.media_proxy", "extract_direct_media_url")
parse_proxy_export_token = load_attr("telegram_mcp.infrastructure.media_proxy", "parse_proxy_export_token")
parse_proxy_media_token = load_attr("telegram_mcp.infrastructure.media_proxy", "parse_proxy_media_token")


def test_build_and_parse_media_proxy_token_roundtrip() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    url = build_proxy_media_url(
        base_url="http://proxy.local",
        chat_id=101,
        message_id=202,
        secret="token-secret",
        ttl_seconds=60,
        now=now,
    )
    token = unquote(urlparse(url).path.rsplit("/", maxsplit=1)[-1])

    target = parse_proxy_media_token(token, secret="token-secret", now=now)

    assert target.chat_id == 101
    assert target.message_id == 202


def test_parse_media_proxy_token_fails_when_expired() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    url = build_proxy_media_url(
        base_url="http://proxy.local",
        chat_id=1,
        message_id=2,
        secret="token-secret",
        ttl_seconds=30,
        now=now,
    )
    token = unquote(urlparse(url).path.rsplit("/", maxsplit=1)[-1])

    with pytest.raises(ValueError, match="expired"):
        parse_proxy_media_token(
            token,
            secret="token-secret",
            now=datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc),
        )


def test_build_and_parse_export_proxy_token_roundtrip() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    url = build_proxy_export_url(
        base_url="http://proxy.local",
        export_id="abc123",
        secret="token-secret",
        ttl_seconds=60,
        now=now,
    )
    token = unquote(urlparse(url).path.rsplit("/", maxsplit=1)[-1])

    target = parse_proxy_export_token(token, secret="token-secret", now=now)

    assert target.export_id == "abc123"


def test_parse_export_proxy_token_fails_when_expired() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    url = build_proxy_export_url(
        base_url="http://proxy.local",
        export_id="abc123",
        secret="token-secret",
        ttl_seconds=30,
        now=now,
    )
    token = unquote(urlparse(url).path.rsplit("/", maxsplit=1)[-1])

    with pytest.raises(ValueError, match="expired"):
        parse_proxy_export_token(
            token,
            secret="token-secret",
            now=datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc),
        )


def test_extract_direct_media_url_prefers_file_url() -> None:
    message = SimpleNamespace(
        file=SimpleNamespace(url="https://cdn.telegram.org/file/abc"),
        media=SimpleNamespace(webpage=SimpleNamespace(url="https://example.org/fallback")),
    )

    assert extract_direct_media_url(message) == "https://cdn.telegram.org/file/abc"


def test_extract_direct_media_url_uses_webpage_url_fallback() -> None:
    message = SimpleNamespace(
        file=SimpleNamespace(url=None),
        media=SimpleNamespace(webpage=SimpleNamespace(url="https://example.org/fallback")),
    )

    assert extract_direct_media_url(message) == "https://example.org/fallback"
