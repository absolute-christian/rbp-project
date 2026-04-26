from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part:
            ids.add(int(part))
    return ids


@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: Path
    admin_ids: set[int]
    admin_chat_id: int | None
    welcome_photo_path: Path


def load_config() -> Config:
    load_dotenv(BASE_DIR / ".env")

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    db_path_raw = os.getenv("DB_PATH", "data/rbp.sqlite3").strip()
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    admin_chat_raw = os.getenv("ADMIN_CHAT_ID", "").strip()
    welcome_photo_raw = os.getenv("WELCOME_PHOTO_PATH", "assets/welcome.jpg").strip()

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required in .env")
    if not admin_ids:
        raise RuntimeError("ADMIN_IDS is required in .env")

    db_path = Path(db_path_raw)
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path

    welcome_photo_path = Path(welcome_photo_raw)
    if not welcome_photo_path.is_absolute():
        welcome_photo_path = BASE_DIR / welcome_photo_path

    return Config(
        bot_token=bot_token,
        db_path=db_path,
        admin_ids=admin_ids,
        admin_chat_id=int(admin_chat_raw) if admin_chat_raw else None,
        welcome_photo_path=welcome_photo_path,
    )
