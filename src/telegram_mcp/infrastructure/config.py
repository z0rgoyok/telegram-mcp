from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class Settings:
    api_id: int
    api_hash: str
    phone: str
    session_path: Path
    dialog_scan_limit: int
    media_download_limit_bytes: int
    media_proxy_host: str
    media_proxy_port: int
    media_proxy_public_base_url: str
    media_proxy_token_secret: str
    media_proxy_token_ttl_seconds: int

    @classmethod
    def from_env(cls) -> Settings:
        api_id_raw = os.environ.get("API_ID", "").strip()
        if not api_id_raw:
            raise RuntimeError("API_ID env var is required")

        api_hash = os.environ.get("API_HASH", "").strip()
        if not api_hash:
            raise RuntimeError("API_HASH env var is required")

        phone = os.environ.get("PHONE", "").strip()
        if not phone:
            raise RuntimeError("PHONE env var is required")

        session_dir = Path(os.environ.get("SESSION_DIR", "var"))
        dialog_scan_limit_raw = os.environ.get("DIALOG_SCAN_LIMIT", "1000").strip()
        media_download_limit_raw = os.environ.get("MEDIA_DOWNLOAD_LIMIT_BYTES", "8388608").strip()
        media_proxy_host = os.environ.get("MEDIA_PROXY_HOST", "0.0.0.0").strip() or "0.0.0.0"
        media_proxy_port_raw = os.environ.get("MEDIA_PROXY_PORT", "8902").strip()
        media_proxy_public_base_url = os.environ.get(
            "MEDIA_PROXY_PUBLIC_BASE_URL",
            f"http://localhost:{media_proxy_port_raw}",
        ).strip()
        media_proxy_token_secret = os.environ.get("MEDIA_PROXY_TOKEN_SECRET", api_hash).strip()
        media_proxy_token_ttl_raw = os.environ.get("MEDIA_PROXY_TOKEN_TTL_SECONDS", "3600").strip()
        try:
            dialog_scan_limit = int(dialog_scan_limit_raw)
        except ValueError as exc:
            raise RuntimeError("DIALOG_SCAN_LIMIT must be an integer") from exc

        try:
            media_download_limit_bytes = int(media_download_limit_raw)
        except ValueError as exc:
            raise RuntimeError("MEDIA_DOWNLOAD_LIMIT_BYTES must be an integer") from exc

        try:
            media_proxy_port = int(media_proxy_port_raw)
        except ValueError as exc:
            raise RuntimeError("MEDIA_PROXY_PORT must be an integer") from exc

        try:
            media_proxy_token_ttl_seconds = int(media_proxy_token_ttl_raw)
        except ValueError as exc:
            raise RuntimeError("MEDIA_PROXY_TOKEN_TTL_SECONDS must be an integer") from exc

        if dialog_scan_limit <= 0:
            raise RuntimeError("DIALOG_SCAN_LIMIT must be positive")
        if media_download_limit_bytes <= 0:
            raise RuntimeError("MEDIA_DOWNLOAD_LIMIT_BYTES must be positive")
        if media_proxy_port <= 0 or media_proxy_port > 65535:
            raise RuntimeError("MEDIA_PROXY_PORT must be in range 1..65535")
        if media_proxy_token_ttl_seconds <= 0:
            raise RuntimeError("MEDIA_PROXY_TOKEN_TTL_SECONDS must be positive")
        proxy_scheme = urlparse(media_proxy_public_base_url).scheme.casefold()
        if proxy_scheme not in {"http", "https"}:
            raise RuntimeError("MEDIA_PROXY_PUBLIC_BASE_URL must use http or https scheme")
        if not media_proxy_token_secret:
            raise RuntimeError("MEDIA_PROXY_TOKEN_SECRET must be non-empty")

        return cls(
            api_id=int(api_id_raw),
            api_hash=api_hash,
            phone=phone,
            session_path=session_dir / "telegram",
            dialog_scan_limit=dialog_scan_limit,
            media_download_limit_bytes=media_download_limit_bytes,
            media_proxy_host=media_proxy_host,
            media_proxy_port=media_proxy_port,
            media_proxy_public_base_url=media_proxy_public_base_url.rstrip("/"),
            media_proxy_token_secret=media_proxy_token_secret,
            media_proxy_token_ttl_seconds=media_proxy_token_ttl_seconds,
        )
