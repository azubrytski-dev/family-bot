from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import AsyncIterator

import psycopg
from psycopg.rows import dict_row

from app.core.models import ChatRecord, SchedulerJob
from app.core.services.activity_service import ActivityRepository
from app.storage.repo import (
    ChatRegistryRepository,
    SchedulerJobRepository,
)


class PgActivityRepository(ActivityRepository):
    """
    Lightweight last-activity tracking using chat_members_activity table.

    One row per (chat_id, user_id) with last message timestamps.
    """

    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[psycopg.AsyncConnection]:
        conn = await psycopg.AsyncConnection.connect(self._postgres_url, autocommit=True)
        try:
            yield conn
        finally:
            await conn.close()

    async def increment_message_count(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
        username: str | None,
        display_name: str | None,
    ) -> None:
        async with self._connection() as conn:
            async with conn.cursor() as cur:
                # Update chat_members_activity
                await cur.execute(
                    """
                    INSERT INTO chat_members_activity (
                        chat_id,
                        user_id,
                        username,
                        display_name,
                        last_message_at,
                        last_message_date,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (chat_id, user_id)
                    DO UPDATE SET
                        username = EXCLUDED.username,
                        display_name = EXCLUDED.display_name,
                        last_message_at = EXCLUDED.last_message_at,
                        last_message_date = EXCLUDED.last_message_date,
                        updated_at = NOW()
                    """,
                    (chat_id, user_id, username, display_name, message_ts, message_ts.date()),
                )
                # Also update daily_activity
                await cur.execute(
                    """
                    INSERT INTO daily_activity (chat_id, user_id, activity_date, message_count, last_message_ts)
                    VALUES (%s, %s, %s, 1, %s)
                    ON CONFLICT (chat_id, user_id, activity_date)
                    DO UPDATE SET message_count = daily_activity.message_count + 1,
                                  last_message_ts = EXCLUDED.last_message_ts
                    """,
                    (chat_id, user_id, message_ts.date(), message_ts),
                )

    async def get_today_activity(self, chat_id: int, day: date) -> dict[int, int]:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT user_id
                    FROM chat_members_activity
                    WHERE chat_id = %s
                      AND last_message_date = %s
                    """,
                    (chat_id, day),
                )
                rows = await cur.fetchall()
        # We only care that the user wrote at least once today.
        return {int(r["user_id"]): 1 for r in rows}

    async def get_chat_members(self, chat_id: int) -> list[int]:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT user_id
                    FROM chat_members_activity
                    WHERE chat_id = %s
                    """,
                    (chat_id,),
                )
                rows = await cur.fetchall()
        return [int(r["user_id"]) for r in rows]

    async def get_chat_member_labels(self, chat_id: int) -> dict[int, str]:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT user_id, username, display_name
                    FROM chat_members_activity
                    WHERE chat_id = %s
                    """,
                    (chat_id,),
                )
                rows = await cur.fetchall()
        labels: dict[int, str] = {}
        for row in rows:
            user_id = int(row["user_id"])
            username = row["username"]
            display_name = row["display_name"]
            if display_name:
                labels[user_id] = display_name
                continue
            if username:
                labels[user_id] = f"@{username}"
                continue
            labels[user_id] = f"id:{user_id}"
        return labels


class PgChatRegistryRepository(ChatRegistryRepository):
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[psycopg.AsyncConnection]:
        conn = await psycopg.AsyncConnection.connect(self._postgres_url, autocommit=True)
        try:
            yield conn
        finally:
            await conn.close()

    async def upsert_chat(
        self,
        chat_id: int,
        title: str | None,
        chat_type: str,
    ) -> None:
        async with self._connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO chats (chat_id, title, chat_type, is_active, is_approved, allow_test, last_seen_at)
                    VALUES (%s, %s, %s, TRUE, FALSE, FALSE, NOW())
                    ON CONFLICT (chat_id)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        chat_type = EXCLUDED.chat_type,
                        is_active = TRUE,
                        is_approved = CASE WHEN chats.is_active THEN chats.is_approved ELSE FALSE END,
                        removed_at = NULL,
                        last_seen_at = NOW()
                    """,
                    (chat_id, title, chat_type),
                )

    async def list_approved_chats(self) -> list[ChatRecord]:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT chat_id, title, chat_type, is_active, is_approved, allow_test, removed_at
                    FROM chats
                    WHERE is_active = TRUE
                      AND is_approved = TRUE
                    ORDER BY last_seen_at DESC
                    """
                )
                rows = await cur.fetchall()
        return [
            ChatRecord(
                chat_id=row["chat_id"],
                title=row["title"],
                chat_type=row["chat_type"],
                is_active=row["is_active"],
                is_approved=row["is_approved"],
                allow_test=row["allow_test"],
                removed_at=row["removed_at"],
            )
            for row in rows
        ]

    async def is_chat_approved(self, chat_id: int) -> bool:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT is_approved
                    FROM chats
                    WHERE chat_id = %s
                    """,
                    (chat_id,),
                )
                row = await cur.fetchone()
        if row is None:
            return False
        return bool(row["is_approved"])

    async def is_chat_test_allowed(self, chat_id: int) -> bool:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT allow_test
                    FROM chats
                    WHERE chat_id = %s
                    """,
                    (chat_id,),
                )
                row = await cur.fetchone()
        if row is None:
            return False
        return bool(row["allow_test"])

    async def mark_chat_removed(self, chat_id: int) -> None:
        async with self._connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE chats
                    SET is_active = FALSE,
                        is_approved = FALSE,
                        removed_at = NOW()
                    WHERE chat_id = %s
                    """,
                    (chat_id,),
                )

    async def migrate_chat(self, old_chat_id: int, new_chat_id: int) -> None:
        async with self._connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO chats (chat_id, title, chat_type, is_active, is_approved, allow_test, removed_at, last_seen_at)
                    SELECT %s,
                           title,
                           'supergroup',
                           TRUE,
                           is_approved,
                           allow_test,
                           NULL,
                           NOW()
                    FROM chats
                    WHERE chat_id = %s
                    ON CONFLICT (chat_id)
                    DO UPDATE SET
                        title = COALESCE(EXCLUDED.title, chats.title),
                        chat_type = 'supergroup',
                        is_active = TRUE,
                        is_approved = chats.is_approved OR EXCLUDED.is_approved,
                        allow_test = chats.allow_test OR EXCLUDED.allow_test,
                        removed_at = NULL,
                        last_seen_at = NOW()
                    """,
                    (new_chat_id, old_chat_id),
                )
                await cur.execute("DELETE FROM chats WHERE chat_id = %s", (old_chat_id,))


class PgSchedulerJobRepository(SchedulerJobRepository):
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[psycopg.AsyncConnection]:
        conn = await psycopg.AsyncConnection.connect(self._postgres_url, autocommit=True)
        try:
            yield conn
        finally:
            await conn.close()

    async def list_enabled_jobs(self) -> list[SchedulerJob]:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT job_key,
                           job_type,
                           cron_hour,
                           cron_minute,
                           timezone_name,
                           chat_id,
                           enabled
                    FROM scheduler_jobs
                    WHERE enabled = TRUE
                    ORDER BY cron_hour, cron_minute, job_key
                    """
                )
                rows = await cur.fetchall()
        return [
            SchedulerJob(
                job_key=row["job_key"],
                job_type=row["job_type"],
                cron_hour=row["cron_hour"],
                cron_minute=row["cron_minute"],
                timezone_name=row["timezone_name"],
                chat_id=row["chat_id"],
                enabled=row["enabled"],
            )
            for row in rows
        ]
