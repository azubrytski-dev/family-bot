from __future__ import annotations

from datetime import datetime, timezone
import os
import time
from typing import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from psycopg.sql import Identifier, SQL

from app.core.config import AppConfig
from app.storage.migrate import run_migrations
from app.storage.pg_repo import (
    PgActivityRepository,
    PgAppConfigRepository,
    PgChatRegistryRepository,
    PgSessionMemoryRepository,
    PgSchedulerJobRepository,
)


TEST_DB_URL_ENV = "TEST_POSTGRES_URL"
DEFAULT_DB_URL_ENV = "POSTGRES_URL"
DROP_TEST_DATABASES_ENV = "DROP_TEST_DATABASES"


def _get_test_postgres_url() -> str:
    url = os.environ.get(TEST_DB_URL_ENV) or os.environ.get(DEFAULT_DB_URL_ENV)
    if not url:
        pytest.skip(
            f"Neither {TEST_DB_URL_ENV} nor {DEFAULT_DB_URL_ENV} is set; skipping database integration tests."
        )
    return url


def _should_drop_test_databases() -> bool:
    return os.environ.get(DROP_TEST_DATABASES_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _run_test_migrations(postgres_url: str) -> None:
    config = AppConfig.model_validate(
        {
            "BOT_TOKEN": "dummy",
            "OPENAI_API_KEY": "test-key",
            "POSTGRES_URL": postgres_url,
        }
    )
    await run_migrations(config=config)


def _get_database_name(postgres_url: str) -> str:
    conninfo = conninfo_to_dict(postgres_url)
    dbname = conninfo.get("dbname")
    if not isinstance(dbname, str) or not dbname:
        raise AssertionError(f"{TEST_DB_URL_ENV} must include a database name.")
    return dbname


def _build_ephemeral_database_name(base_postgres_url: str) -> str:
    base_database_name = _get_database_name(base_postgres_url)
    ephemeral_database_name = f"{base_database_name}_{time.time_ns()}"
    if ephemeral_database_name == base_database_name:
        raise AssertionError("Ephemeral test database name must differ from the base database name.")
    return ephemeral_database_name


def _get_admin_conninfo(postgres_url: str) -> str:
    return make_conninfo(postgres_url, dbname="postgres")


async def _create_database_if_missing(postgres_url: str) -> None:
    dbname = _get_database_name(postgres_url)
    admin_conninfo = _get_admin_conninfo(postgres_url)

    async with await psycopg.AsyncConnection.connect(admin_conninfo, autocommit=True) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            exists = await cur.fetchone()
            if exists is None:
                await cur.execute(SQL("CREATE DATABASE {}").format(Identifier(dbname)))


async def _drop_database(postgres_url: str) -> None:
    dbname = _get_database_name(postgres_url)
    admin_conninfo = _get_admin_conninfo(postgres_url)

    async with await psycopg.AsyncConnection.connect(admin_conninfo, autocommit=True) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (dbname,),
            )
            await cur.execute(SQL("DROP DATABASE IF EXISTS {}").format(Identifier(dbname)))


@pytest_asyncio.fixture
async def test_database_url() -> AsyncIterator[str]:
    base_postgres_url = _get_test_postgres_url()
    # Use the configured URL only as a connection template.
    # Every test execution gets its own fresh database name derived from that base.
    ephemeral_db_name = _build_ephemeral_database_name(base_postgres_url)
    postgres_url = make_conninfo(base_postgres_url, dbname=ephemeral_db_name)

    await _create_database_if_missing(postgres_url)
    await _run_test_migrations(postgres_url)

    try:
        yield postgres_url
    finally:
        if _should_drop_test_databases():
            await _drop_database(postgres_url)


def test_build_ephemeral_database_name_uses_base_name_as_prefix_only():
    base_postgres_url = "postgresql://postgres:postgres@localhost:5432/family_bot"

    ephemeral_database_name = _build_ephemeral_database_name(base_postgres_url)

    assert ephemeral_database_name.startswith("family_bot_")
    assert ephemeral_database_name != "family_bot"


@pytest.mark.asyncio
async def test_pg_chat_registry_repo(test_database_url: str):
    repo = PgChatRegistryRepository(test_database_url)

    test_chat_id = 999999  # Use a unique ID to avoid conflicts
    await repo.upsert_chat(chat_id=test_chat_id, title="Test Chat", chat_type="group")

    conn = await psycopg.AsyncConnection.connect(test_database_url)
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT chat_id, title, chat_type, is_active, is_approved, allow_test, removed_at FROM chats WHERE chat_id = %s",
            (test_chat_id,),
        )
        row = await cur.fetchone()
    assert row is not None
    assert row["title"] == "Test Chat"
    assert row["chat_type"] == "group"
    assert row["is_active"] is True
    assert row["is_approved"] is False
    assert row["allow_test"] is False
    assert row["removed_at"] is None

    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM chats WHERE chat_id = %s", (test_chat_id,))

    await conn.close()


@pytest.mark.asyncio
async def test_pg_activity_repo(test_database_url: str):
    repo = PgActivityRepository(test_database_url)

    test_chat_id = 900000 + (uuid4().int % 10000)
    test_user_id = 100000 + (uuid4().int % 10000)
    now = datetime.now(timezone.utc)

    await repo.increment_message_count(
        chat_id=test_chat_id,
        user_id=test_user_id,
        message_ts=now,
        activity_date=today,
        username="testuser",
        display_name="Test User",
    )

    today = now.date()
    activity = await repo.get_today_activity(test_chat_id, today)
    assert activity == {test_user_id: 1}

    conn = await psycopg.AsyncConnection.connect(test_database_url)
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
async def test_pg_scheduler_job_repo(test_database_url: str):
    repo = PgSchedulerJobRepository(test_database_url)
    jobs = await repo.list_enabled_jobs()

    assert any(job.job_key == "good_morning" for job in jobs)
    assert any(job.job_type == "good_night_and_activity" for job in jobs)


@pytest.mark.asyncio
async def test_pg_app_config_repo_lists_enabled_values(test_database_url: str):
    repo = PgAppConfigRepository(test_database_url)
    conn = await psycopg.AsyncConnection.connect(test_database_url)

    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO app_config (parameter, value, is_enabled)
            VALUES
                ('weather.city', 'Minsk', TRUE),
                ('weather.city', 'Tbilisi', FALSE),
                ('weather.city', 'Batumi', TRUE),
                ('other.key', 'Ignored', TRUE)
            """
        )
    await conn.commit()

    values = await repo.list_enabled_values("weather.city")

    assert values == ["Minsk", "Batumi"]

    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM app_config")
    await conn.close()


@pytest.mark.asyncio
async def test_pg_chat_registry_lists_only_approved_chats(test_database_url: str):
    conn = await psycopg.AsyncConnection.connect(test_database_url)

    repo = PgChatRegistryRepository(test_database_url)
    test_chat_id = 800000 + (uuid4().int % 10000)

    await repo.upsert_chat(chat_id=test_chat_id, title="Greeting Chat", chat_type="group")
    assert await repo.is_chat_approved(test_chat_id) is False

    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE chats SET is_approved = TRUE WHERE chat_id = %s",
            (test_chat_id,),
        )
    await conn.commit()

    chats = await repo.list_approved_chats()

    assert any(chat.chat_id == test_chat_id and chat.title == "Greeting Chat" for chat in chats)

    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM chats WHERE chat_id = %s", (test_chat_id,))
    await conn.close()


@pytest.mark.asyncio
async def test_pg_session_memory_repo_archives_session_and_deletes_messages(test_database_url: str):
    repo = PgSessionMemoryRepository(test_database_url)
    started_at = datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc)
    expires_at = datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc)

    session = await repo.create_session(
        chat_id=701,
        local_date=started_at.date(),
        started_at_utc=started_at,
        expires_at_utc=expires_at,
    )
    await repo.add_message(
        chat_id=701,
        session_id=session.id,
        telegram_message_id=1001,
        user_id=501,
        username="andrei",
        display_name="Andrei",
        message_text="Собираемся в поездку",
        message_ts_utc=started_at,
        local_date=started_at.date(),
        is_reply_to_bot=True,
    )

    messages = await repo.list_session_messages(session.id)
    assert len(messages) == 1
    assert messages[0].is_reply_to_bot is True

    await repo.archive_session(
        session_id=session.id,
        completed_at_utc=expires_at,
        summary_text="Андрей обсуждал планы на поездку.",
    )

    conn = await psycopg.AsyncConnection.connect(test_database_url)
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT status, completed_at_utc, summary_text, message_count
            FROM chat_sessions
            WHERE id = %s
            """,
            (session.id,),
        )
        row = await cur.fetchone()
        await cur.execute("SELECT COUNT(*) AS count FROM chat_messages WHERE session_id = %s", (session.id,))
        message_row = await cur.fetchone()
    await conn.close()

    assert row is not None
    assert row["status"] == "completed"
    assert row["completed_at_utc"] == expires_at
    assert row["summary_text"] == "Андрей обсуждал планы на поездку."
    assert row["message_count"] == 1
    assert message_row is not None
    assert message_row["count"] == 0


@pytest.mark.asyncio
async def test_pg_session_memory_repo_lists_completed_sessions_for_date(test_database_url: str):
    repo = PgSessionMemoryRepository(test_database_url)
    started_at = datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc)
    expires_at = datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc)

    session = await repo.create_session(
        chat_id=702,
        local_date=started_at.date(),
        started_at_utc=started_at,
        expires_at_utc=expires_at,
    )
    await repo.add_message(
        chat_id=702,
        session_id=session.id,
        telegram_message_id=1002,
        user_id=501,
        username="andrei",
        display_name="Andrei",
        message_text="Планы на утро",
        message_ts_utc=started_at,
        local_date=started_at.date(),
        is_reply_to_bot=False,
    )
    await repo.archive_session(
        session_id=session.id,
        completed_at_utc=expires_at,
        summary_text="Обсуждали планы на утро.",
    )

    sessions = await repo.list_completed_sessions_for_date(chat_id=702, local_date=started_at.date())

    assert len(sessions) == 1
    assert sessions[0].summary_text == "Обсуждали планы на утро."


@pytest.mark.asyncio
async def test_pg_chat_registry_test_flag_defaults_to_false_and_can_be_enabled(test_database_url: str):
    conn = await psycopg.AsyncConnection.connect(test_database_url)

    repo = PgChatRegistryRepository(test_database_url)
    test_chat_id = 600000 + (uuid4().int % 10000)

    await repo.upsert_chat(chat_id=test_chat_id, title="Test Flag Chat", chat_type="group")
    assert await repo.is_chat_test_allowed(test_chat_id) is False

    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE chats SET allow_test = TRUE WHERE chat_id = %s",
            (test_chat_id,),
        )
    await conn.commit()

    assert await repo.is_chat_test_allowed(test_chat_id) is True

    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM chats WHERE chat_id = %s", (test_chat_id,))

    await conn.close()


@pytest.mark.asyncio
async def test_pg_chat_registry_marks_removed_and_requires_reapproval_on_return(test_database_url: str):
    conn = await psycopg.AsyncConnection.connect(test_database_url)

    repo = PgChatRegistryRepository(test_database_url)
    test_chat_id = 700000 + (uuid4().int % 10000)

    await repo.upsert_chat(chat_id=test_chat_id, title="Lifecycle Chat", chat_type="group")
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE chats SET is_approved = TRUE WHERE chat_id = %s",
            (test_chat_id,),
        )
    await conn.commit()

    await repo.mark_chat_removed(test_chat_id)
    assert await repo.is_chat_approved(test_chat_id) is False

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT is_active, is_approved, removed_at FROM chats WHERE chat_id = %s",
            (test_chat_id,),
        )
        removed_row = await cur.fetchone()
    assert removed_row is not None
    assert removed_row["is_active"] is False
    assert removed_row["is_approved"] is False
    assert removed_row["removed_at"] is not None

    await repo.upsert_chat(chat_id=test_chat_id, title="Lifecycle Chat", chat_type="group")

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT is_active, is_approved, removed_at FROM chats WHERE chat_id = %s",
            (test_chat_id,),
        )
        readded_row = await cur.fetchone()
    assert readded_row is not None
    assert readded_row["is_active"] is True
    assert readded_row["is_approved"] is False
    assert readded_row["removed_at"] is None

    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM chats WHERE chat_id = %s", (test_chat_id,))

    await conn.close()


@pytest.mark.asyncio
async def test_pg_chat_registry_migrates_group_chat_to_supergroup(test_database_url: str):
    conn = await psycopg.AsyncConnection.connect(test_database_url)

    repo = PgChatRegistryRepository(test_database_url)
    old_chat_id = 500001
    new_chat_id = -100500001

    await repo.upsert_chat(chat_id=old_chat_id, title="Migrated Chat", chat_type="group")
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE chats SET is_approved = TRUE, allow_test = TRUE WHERE chat_id = %s",
            (old_chat_id,),
        )
    await conn.commit()

    await repo.migrate_chat(old_chat_id, new_chat_id)

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT chat_id, chat_type, is_active, is_approved, allow_test, removed_at
            FROM chats
            WHERE chat_id = %s
            """,
            (new_chat_id,),
        )
        migrated_row = await cur.fetchone()
        await cur.execute("SELECT 1 FROM chats WHERE chat_id = %s", (old_chat_id,))
        old_row = await cur.fetchone()

    assert migrated_row is not None
    assert migrated_row["chat_id"] == new_chat_id
    assert migrated_row["chat_type"] == "supergroup"
    assert migrated_row["is_active"] is True
    assert migrated_row["is_approved"] is True
    assert migrated_row["allow_test"] is True
    assert migrated_row["removed_at"] is None
    assert old_row is None

    await conn.close()


@pytest.mark.asyncio
async def test_connection_string(test_database_url: str):
    try:
        conn = await psycopg.AsyncConnection.connect(test_database_url)
        await conn.close()
        assert True
    except Exception:
        assert False, f"Failed to connect to the configured test database from {TEST_DB_URL_ENV}"
