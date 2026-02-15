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

    @classmethod
    def from_env(cls) -> Settings:
        api_id_raw = os.environ.get("API_ID", "")
        if not api_id_raw.strip():
            raise RuntimeError("API_ID env var is required")

        api_hash = os.environ.get("API_HASH", "")
        if not api_hash.strip():
            raise RuntimeError("API_HASH env var is required")

        phone = os.environ.get("PHONE", "")
        if not phone.strip():
            raise RuntimeError("PHONE env var is required")

        session_dir = Path(os.environ.get("SESSION_DIR", "var"))
        return cls(
            api_id=int(api_id_raw),
            api_hash=api_hash,
            phone=phone,
            session_path=session_dir / "telegram",
        )
