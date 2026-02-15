from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    api_id: int
    api_hash: str
    phone: str
    session_path: Path
    dialog_scan_limit: int

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
        try:
            dialog_scan_limit = int(dialog_scan_limit_raw)
        except ValueError as exc:
            raise RuntimeError("DIALOG_SCAN_LIMIT must be an integer") from exc

        if dialog_scan_limit <= 0:
            raise RuntimeError("DIALOG_SCAN_LIMIT must be positive")

        return cls(
            api_id=int(api_id_raw),
            api_hash=api_hash,
            phone=phone,
            session_path=session_dir / "telegram",
            dialog_scan_limit=dialog_scan_limit,
        )
