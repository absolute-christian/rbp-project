from __future__ import annotations

from pathlib import Path
from typing import Any

import aiosqlite
from aiogram.types import User


class Database:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self._db_path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.execute("PRAGMA journal_mode = WAL")
        await self.conn.execute("PRAGMA synchronous = NORMAL")
        await self.conn.execute("PRAGMA busy_timeout = 5000")
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def init_schema(self) -> None:
        assert self.conn is not None
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_bot INTEGER NOT NULL DEFAULT 0,
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_blocked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                type TEXT NOT NULL CHECK (type IN ('complaint', 'application')),
                kind_label TEXT,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'reviewing', 'approved', 'rejected')),
                admin_chat_id INTEGER,
                admin_message_id INTEGER,
                user_status_message_id INTEGER,
                review_admin_id INTEGER,
                review_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_users_broadcast
                ON users(user_id)
                WHERE is_blocked = 0;

            CREATE INDEX IF NOT EXISTS idx_tickets_user_active
                ON tickets(user_id, status)
                WHERE status IN ('pending', 'reviewing');

            CREATE INDEX IF NOT EXISTS idx_tickets_created
                ON tickets(created_at DESC);
            """
        )
        await self._ensure_ticket_columns()
        await self.conn.commit()

    async def execute(self, query: str, *args: Any) -> None:
        assert self.conn is not None
        await self.conn.execute(query, args)
        await self.conn.commit()

    async def fetchrow(self, query: str, *args: Any) -> aiosqlite.Row | None:
        assert self.conn is not None
        cursor = await self.conn.execute(query, args)
        try:
            return await cursor.fetchone()
        finally:
            await cursor.close()

    async def fetch(self, query: str, *args: Any) -> list[aiosqlite.Row]:
        assert self.conn is not None
        cursor = await self.conn.execute(query, args)
        try:
            return await cursor.fetchall()
        finally:
            await cursor.close()

    async def upsert_user(self, user: User, is_admin: bool = False) -> None:
        await self.execute(
            """
            INSERT INTO users (user_id, username, first_name, last_name, is_bot, is_admin)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                is_bot = excluded.is_bot,
                is_admin = excluded.is_admin,
                is_blocked = 0,
                updated_at = CURRENT_TIMESTAMP
            """,
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            int(user.is_bot),
            int(is_admin),
        )

    async def has_active_ticket(self, user_id: int) -> aiosqlite.Row | None:
        return await self.fetchrow(
            """
            SELECT id, type, status
            FROM tickets
            WHERE user_id = ? AND status IN ('pending', 'reviewing')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )

    async def create_ticket(
        self,
        user_id: int,
        ticket_type: str,
        body: str,
        kind_label: str | None = None,
    ) -> aiosqlite.Row:
        row = await self.fetchrow(
            """
            INSERT INTO tickets (user_id, type, body, kind_label)
            VALUES (?, ?, ?, ?)
            RETURNING *
            """,
            user_id,
            ticket_type,
            body,
            kind_label,
        )
        await self._commit()
        assert row is not None
        return row

    async def set_ticket_admin_message(
        self,
        ticket_id: int,
        admin_chat_id: int,
        admin_message_id: int,
    ) -> None:
        await self.execute(
            """
            UPDATE tickets
            SET admin_chat_id = ?,
                admin_message_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            admin_chat_id,
            admin_message_id,
            ticket_id,
        )

    async def set_ticket_user_status_message(
        self,
        ticket_id: int,
        message_id: int,
    ) -> None:
        await self.execute(
            """
            UPDATE tickets
            SET user_status_message_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            message_id,
            ticket_id,
        )

    async def get_ticket(self, ticket_id: int) -> aiosqlite.Row | None:
        return await self.fetchrow(
            """
            SELECT t.*, u.username, u.first_name, u.last_name
            FROM tickets t
            JOIN users u ON u.user_id = t.user_id
            WHERE t.id = ?
            """,
            ticket_id,
        )

    async def finish_pending_ticket(
        self,
        ticket_id: int,
        status: str,
        admin_id: int,
        note: str | None = None,
    ) -> aiosqlite.Row | None:
        row = await self.fetchrow(
            """
            UPDATE tickets
            SET status = ?,
                review_admin_id = ?,
                review_note = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending'
            RETURNING *
            """,
            status,
            admin_id,
            note,
            ticket_id,
        )
        await self._commit()
        return row

    async def lock_application_for_review(
        self,
        ticket_id: int,
        admin_id: int,
    ) -> aiosqlite.Row | None:
        row = await self.fetchrow(
            """
            UPDATE tickets
            SET status = 'reviewing',
                review_admin_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending' AND type = 'application'
            RETURNING *
            """,
            admin_id,
            ticket_id,
        )
        await self._commit()
        return row

    async def finish_reviewing_application(
        self,
        ticket_id: int,
        admin_id: int,
        status: str,
        note: str,
    ) -> aiosqlite.Row | None:
        row = await self.fetchrow(
            """
            UPDATE tickets
            SET status = ?,
                review_note = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND review_admin_id = ?
              AND status = 'reviewing'
              AND type = 'application'
            RETURNING *
            """,
            status,
            note,
            ticket_id,
            admin_id,
        )
        await self._commit()
        return row

    async def close_ticket(
        self,
        ticket_id: int,
        admin_id: int,
    ) -> aiosqlite.Row | None:
        row = await self.fetchrow(
            """
            UPDATE tickets
            SET status = 'rejected',
                review_admin_id = ?,
                review_note = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status IN ('pending', 'reviewing')
            RETURNING *
            """,
            admin_id,
            ticket_id,
        )
        await self._commit()
        return row

    async def get_all_broadcast_users(self) -> list[int]:
        rows = await self.fetch(
            "SELECT user_id FROM users WHERE is_blocked = 0 ORDER BY user_id"
        )
        return [int(row["user_id"]) for row in rows]

    async def mark_user_blocked(self, user_id: int) -> None:
        await self.execute(
            "UPDATE users SET is_blocked = 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            user_id,
        )

    async def stats(self) -> aiosqlite.Row:
        row = await self.fetchrow(
            """
            SELECT
                (SELECT count(*) FROM users) AS users_total,
                (SELECT count(*) FROM users WHERE is_blocked = 0) AS users_active,
                (SELECT count(*) FROM tickets WHERE type = 'complaint') AS complaints_total,
                (SELECT count(*) FROM tickets WHERE type = 'application') AS applications_total,
                (SELECT count(*) FROM tickets WHERE status IN ('pending', 'reviewing')) AS tickets_active
            """
        )
        assert row is not None
        return row

    async def _commit(self) -> None:
        assert self.conn is not None
        await self.conn.commit()

    async def _ensure_ticket_columns(self) -> None:
        assert self.conn is not None
        cursor = await self.conn.execute("PRAGMA table_info(tickets)")
        try:
            columns = {row["name"] for row in await cursor.fetchall()}
        finally:
            await cursor.close()

        if "user_status_message_id" not in columns:
            await self.conn.execute("ALTER TABLE tickets ADD COLUMN user_status_message_id INTEGER")
        if "kind_label" not in columns:
            await self.conn.execute("ALTER TABLE tickets ADD COLUMN kind_label TEXT")
