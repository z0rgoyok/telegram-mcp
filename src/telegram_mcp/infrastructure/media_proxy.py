from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import quote, urlparse


@dataclass(frozen=True, slots=True)
class MediaProxyTarget:
    chat_id: int
    message_id: int


@dataclass(frozen=True, slots=True)
class ExportProxyTarget:
    export_id: str


def extract_direct_media_url(message: object) -> str | None:
    message_payload = cast(Any, message)
    file_ref = message_payload.file if hasattr(message_payload, "file") else None
    direct_from_file = _optional_http_url(_attr(file_ref, "url"))
    if direct_from_file is not None:
        return direct_from_file

    raw_media = message_payload.media if hasattr(message_payload, "media") else None
    webpage = _attr(raw_media, "webpage")
    direct_from_webpage = _optional_http_url(_attr(webpage, "url"))
    if direct_from_webpage is not None:
        return direct_from_webpage

    return None


def build_proxy_media_url(
    *,
    base_url: str,
    chat_id: int,
    message_id: int,
    secret: str,
    ttl_seconds: int,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    expires_at = int((issued_at + timedelta(seconds=ttl_seconds)).timestamp())
    return _build_signed_proxy_url(
        base_url=base_url,
        route="media",
        payload={"c": chat_id, "m": message_id, "e": expires_at},
        secret=secret,
    )


def parse_proxy_media_token(
    token: str,
    *,
    secret: str,
    now: datetime | None = None,
) -> MediaProxyTarget:
    payload_token, signature_token = _split_token(token)
    expected_signature = _urlsafe_b64encode(_sign_payload(payload_token, secret))
    if not hmac.compare_digest(signature_token, expected_signature):
        raise ValueError("Invalid media token signature")

    payload_raw = _urlsafe_b64decode(payload_token)
    payload = json.loads(payload_raw.decode("utf-8"))
    chat_id = payload.get("c")
    message_id = payload.get("m")
    expires_at = payload.get("e")
    if not isinstance(chat_id, int) or not isinstance(message_id, int) or not isinstance(expires_at, int):
        raise ValueError("Invalid media token payload")

    current_ts = int((now or datetime.now(UTC)).timestamp())
    if expires_at < current_ts:
        raise ValueError("Media token expired")

    return MediaProxyTarget(chat_id=chat_id, message_id=message_id)


def build_proxy_export_url(
    *,
    base_url: str,
    export_id: str,
    secret: str,
    ttl_seconds: int,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    expires_at = int((issued_at + timedelta(seconds=ttl_seconds)).timestamp())
    return _build_signed_proxy_url(
        base_url=base_url,
        route="exports",
        payload={"e": expires_at, "x": export_id},
        secret=secret,
    )


def _build_signed_proxy_url(
    *,
    base_url: str,
    route: str,
    payload: dict[str, int | str],
    secret: str,
) -> str:
    serialized_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_token = _urlsafe_b64encode(serialized_payload)
    signature = _urlsafe_b64encode(_sign_payload(payload_token, secret))
    token = f"{payload_token}.{signature}"
    return f"{base_url}/{route}/{quote(token, safe='')}"


def parse_proxy_export_token(
    token: str,
    *,
    secret: str,
    now: datetime | None = None,
) -> ExportProxyTarget:
    payload_token, signature_token = _split_token(token)
    expected_signature = _urlsafe_b64encode(_sign_payload(payload_token, secret))
    if not hmac.compare_digest(signature_token, expected_signature):
        raise ValueError("Invalid export token signature")

    payload_raw = _urlsafe_b64decode(payload_token)
    payload = json.loads(payload_raw.decode("utf-8"))
    export_id = payload.get("x")
    expires_at = payload.get("e")
    if not isinstance(export_id, str) or not export_id or not isinstance(expires_at, int):
        raise ValueError("Invalid export token payload")

    current_ts = int((now or datetime.now(UTC)).timestamp())
    if expires_at < current_ts:
        raise ValueError("Export token expired")

    return ExportProxyTarget(export_id=export_id)


def _sign_payload(payload_token: str, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), payload_token.encode("ascii"), hashlib.sha256).digest()


def _split_token(token: str) -> tuple[str, str]:
    left, sep, right = token.partition(".")
    if not sep or not left or not right:
        raise ValueError("Invalid media token format")
    return left, right


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _optional_http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc:
        return normalized
    return None


def _attr(source: object, name: str) -> object:
    if source is None:
        return None
    if hasattr(source, name):
        return getattr(source, name)
    return None
