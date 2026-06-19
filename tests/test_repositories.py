from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import psycopg
from psycopg.rows import dict_row

from app.core.config import get_config
from app.storage.migrate import run_migrations
from app.storage.pg_repo import (
    PgActivityRepository,
    PgChatRegistryRepository,
    PgSchedulerJobRepository,
)


@pytest.mark.asyncio
async def test_pg_chat_registry_repo():
    await run_migrations()
    config = get_config()
    conn = await psycopg.AsyncConnection.connect(config.postgres_url)

    repo = PgChatRegistryRepository(conn)

    test_chat_id = 999999  # Use a unique ID to avoid conflicts
    await repo.upsert_chat(chat_id=test_chat_id, title="Test Chat", chat_type="group")

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT chat_id, title, chat_type, is_active FROM chats WHERE chat_id = %s",
            (test_chat_id,),
        )
        row = await cur.fetchone()
    assert row is not None
    assert row["title"] == "Test Chat"
    assert row["chat_type"] == "group"
    assert row["is_active"] is True

    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM chats WHERE chat_id = %s", (test_chat_id,))

    await conn.close()


@pytest.mark.asyncio
async def test_pg_activity_repo():
    await run_migrations()
    config = get_config()
    conn = await psycopg.AsyncConnection.connect(config.postgres_url)

    repo = PgActivityRepository(conn)

    test_chat_id = 900000 + (uuid4().int % 10000)
    test_user_id = 100000 + (uuid4().int % 10000)
    now = datetime.now(timezone.utc)

    await repo.increment_message_count(
        chat_id=test_chat_id,
        user_id=test_user_id,
        message_ts=now,
        username="testuser",
        display_name="Test User",
    )

    today = now.date()
    activity = await repo.get_today_activity(test_chat_id, today)
    assert activity == {test_user_id: 1}

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT message_count FROM daily_activity WHERE chat_id = %s AND user_id = %s AND activity_date = %s",
            (test_chat_id, test_user_id, today),
        )
        row = await cur.fetchone()
    assert row is not None
    assert row["message_count"] == 1

    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM chat_members_activity WHERE chat_id = %s AND user_id = %s", (test_chat_id, test_user_id))
        await cur.execute("DELETE FROM daily_activity WHERE chat_id = %s AND user_id = %s AND activity_date = %s", (test_chat_id, test_user_id, today))

    await conn.close()


@pytest.mark.asyncio
async def test_pg_scheduler_job_repo():
    await run_migrations()
    config = get_config()
    conn = await psycopg.AsyncConnection.connect(config.postgres_url)

    repo = PgSchedulerJobRepository(conn)
    jobs = await repo.list_enabled_jobs()

    assert any(job.job_key == "good_morning" for job in jobs)
    assert any(job.job_type == "good_night_and_activity" for job in jobs)

    await conn.close()


@pytest.mark.asyncio
async def test_pg_chat_registry_lists_active_chats():
    await run_migrations()
    config = get_config()
    conn = await psycopg.AsyncConnection.connect(config.postgres_url)

    repo = PgChatRegistryRepository(conn)
    test_chat_id = 800000 + (uuid4().int % 10000)

    await repo.upsert_chat(chat_id=test_chat_id, title="Greeting Chat", chat_type="group")
    chats = await repo.list_active_chats()

    assert any(chat.chat_id == test_chat_id and chat.title == "Greeting Chat" for chat in chats)

    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM chats WHERE chat_id = %s", (test_chat_id,))

    await conn.close()


@pytest.mark.asyncio
async def test_connection_string():
    await run_migrations()
    config = get_config()
    try:
        conn = await psycopg.AsyncConnection.connect(config.postgres_url)
        await conn.close()
        assert True
    except Exception:
        assert False, "Failed to connect to database with the configured URL"
