from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import AsyncIterator

import psycopg
from psycopg.rows import dict_row

from app.core.models import ChatRecord, ChatSession, SchedulerJob, SessionMessage
from app.core.services.activity_service import ActivityRepository
from app.storage.repo import (
    AppConfigRepository,
    ChatRegistryRepository,
    SchedulerJobRepository,
    SessionMemoryRepository,
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


class PgAppConfigRepository(AppConfigRepository):
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[psycopg.AsyncConnection]:
        conn = await psycopg.AsyncConnection.connect(self._postgres_url, autocommit=True)
        try:
            yield conn
        finally:
            await conn.close()

    async def list_enabled_values(self, parameter: str) -> list[str]:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT value
                    FROM app_config
                    WHERE parameter = %s
                      AND is_enabled = TRUE
                    ORDER BY id
                    """,
                    (parameter,),
                )
                rows = await cur.fetchall()
        return [str(row["value"]) for row in rows]


class PgSessionMemoryRepository(SessionMemoryRepository):
    def __init__(self, postgres_url: str) -> None:
        self._postgres_url = postgres_url

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[psycopg.AsyncConnection]:
        conn = await psycopg.AsyncConnection.connect(self._postgres_url, autocommit=True)
        try:
            yield conn
        finally:
            await conn.close()

    async def get_open_session(self, chat_id: int) -> ChatSession | None:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id,
                           chat_id,
                           local_date,
                           started_at_utc,
                           expires_at_utc,
                           completed_at_utc,
                           status,
                           message_count,
                           summary_text
                    FROM chat_sessions
                    WHERE chat_id = %s
                      AND status = 'open'
                    """,
                    (chat_id,),
                )
                row = await cur.fetchone()
        if row is None:
            return None
        return _row_to_chat_session(row)

    async def create_session(
        self,
        chat_id: int,
        local_date: date,
        started_at_utc: datetime,
        expires_at_utc: datetime,
    ) -> ChatSession:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO chat_sessions (
                        chat_id,
                        local_date,
                        started_at_utc,
                        expires_at_utc,
                        status,
                        message_count
                    )
                    VALUES (%s, %s, %s, %s, 'open', 0)
                    RETURNING id,
                              chat_id,
                              local_date,
                              started_at_utc,
                              expires_at_utc,
                              completed_at_utc,
                              status,
                              message_count,
                              summary_text
                    """,
                    (chat_id, local_date, started_at_utc, expires_at_utc),
                )
                row = await cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to create chat session.")
        return _row_to_chat_session(row)

    async def add_message(
        self,
        *,
        chat_id: int,
        session_id: int,
        telegram_message_id: int,
        user_id: int,
        username: str | None,
        display_name: str | None,
        message_text: str,
        message_ts_utc: datetime,
        local_date: date,
        is_reply_to_bot: bool,
    ) -> None:
        async with self._connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO chat_messages (
                            chat_id,
                            session_id,
                            telegram_message_id,
                            user_id,
                            username,
                            display_name,
                            message_text,
                            message_ts_utc,
                            local_date,
                            is_reply_to_bot
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (chat_id, telegram_message_id) DO NOTHING
                        """,
                        (
                            chat_id,
                            session_id,
                            telegram_message_id,
                            user_id,
                            username,
                            display_name,
                            message_text,
                            message_ts_utc,
                            local_date,
                            is_reply_to_bot,
                        ),
                    )
                    await cur.execute(
                        """
                        UPDATE chat_sessions
                        SET message_count = (
                                SELECT COUNT(*)
                                FROM chat_messages
                                WHERE session_id = %s
                            ),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (session_id, session_id),
                    )

    async def list_expired_open_sessions(self, as_of_utc: datetime) -> list[ChatSession]:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id,
                           chat_id,
                           local_date,
                           started_at_utc,
                           expires_at_utc,
                           completed_at_utc,
                           status,
                           message_count,
                           summary_text
                    FROM chat_sessions
                    WHERE status = 'open'
                      AND expires_at_utc <= %s
                    ORDER BY expires_at_utc, id
                    """,
                    (as_of_utc,),
                )
                rows = await cur.fetchall()
        return [_row_to_chat_session(row) for row in rows]

    async def list_session_messages(self, session_id: int) -> list[SessionMessage]:
        async with self._connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id,
                           session_id,
                           chat_id,
                           telegram_message_id,
                           user_id,
                           username,
                           display_name,
                           message_text,
                           message_ts_utc,
                           local_date,
                           is_reply_to_bot
                    FROM chat_messages
                    WHERE session_id = %s
                    ORDER BY message_ts_utc, id
                    """,
                    (session_id,),
                )
                rows = await cur.fetchall()
        return [_row_to_session_message(row) for row in rows]

    async def archive_session(
        self,
        *,
        session_id: int,
        completed_at_utc: datetime,
        summary_text: str,
    ) -> None:
        async with self._connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE chat_sessions
                        SET status = 'completed',
                            completed_at_utc = %s,
                            summary_text = %s,
                            message_count = (
                                SELECT COUNT(*)
                                FROM chat_messages
                                WHERE session_id = %s
                            ),
                            updated_at = NOW()
                        WHERE id = %s
                          AND status = 'open'
                        """,
                        (completed_at_utc, summary_text, session_id, session_id),
                    )
                    await cur.execute(
                        """
                        DELETE FROM chat_messages
                        WHERE session_id = %s
                        """,
                        (session_id,),
                    )


def _row_to_chat_session(row: dict) -> ChatSession:
    return ChatSession(
        id=int(row["id"]),
        chat_id=int(row["chat_id"]),
        local_date=row["local_date"],
        started_at_utc=row["started_at_utc"],
        expires_at_utc=row["expires_at_utc"],
        completed_at_utc=row["completed_at_utc"],
        status=str(row["status"]),
        message_count=int(row["message_count"]),
        summary_text=row["summary_text"],
    )


def _row_to_session_message(row: dict) -> SessionMessage:
    return SessionMessage(
        id=int(row["id"]),
        session_id=int(row["session_id"]),
        chat_id=int(row["chat_id"]),
        telegram_message_id=int(row["telegram_message_id"]),
        user_id=int(row["user_id"]),
        username=row["username"],
        display_name=row["display_name"],
        message_text=str(row["message_text"]),
        message_ts_utc=row["message_ts_utc"],
        local_date=row["local_date"],
        is_reply_to_bot=bool(row["is_reply_to_bot"]),
    )
