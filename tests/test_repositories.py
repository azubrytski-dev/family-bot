from __future__ import annotations

import pytest
import psycopg
from psycopg.rows import dict_row

from app.core.config import get_config
from app.storage.pg_repo import (
    PgActivityRepository,
    PgChatRegistryRepository,
    PgCurrencyRepository,
    PgWeatherRepository,
)


@pytest.mark.asyncio
async def test_pg_chat_registry_repo():
    config = get_config()
    conn = await psycopg.AsyncConnection.connect(config.postgres_url)
    
    repo = PgChatRegistryRepository(conn)
    
    # Test upsert chat
    test_chat_id = 999999  # Use a unique ID to avoid conflicts
    await repo.upsert_chat(chat_id=test_chat_id, title="Test Chat", chat_type="group")
    
    # Test list active chats
    chats = list(await repo.list_active_chats())
    assert any(c.chat_id == test_chat_id and c.title == "Test Chat" for c in chats)
    
    # Clean up
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM chats WHERE chat_id = %s", (test_chat_id,))
    
    await conn.close()


@pytest.mark.asyncio
async def test_pg_activity_repo():
    config = get_config()
    conn = await psycopg.AsyncConnection.connect(config.postgres_url)
    
    repo = PgActivityRepository(conn)
    
    # Test increment message count
    from datetime import datetime, timezone
    test_chat_id = 999999
    test_user_id = 12345
    now = datetime.now(timezone.utc)
    
    await repo.increment_message_count(
        chat_id=test_chat_id,
        user_id=test_user_id,
        message_ts=now,
        username="testuser",
        display_name="Test User",
    )
    
    # Test get today activity
    today = now.date()
    activity = await repo.get_today_activity(test_chat_id, today)
    assert test_user_id in activity
    assert activity[test_user_id] == 1  # As per implementation
    
    # Also check daily_activity
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT message_count FROM daily_activity WHERE chat_id = %s AND user_id = %s AND activity_date = %s",
            (test_chat_id, test_user_id, today),
        )
        row = await cur.fetchone()
    assert row is not None
    assert row["message_count"] == 1
    
    # Clean up
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM chat_members_activity WHERE chat_id = %s AND user_id = %s", (test_chat_id, test_user_id))
        await cur.execute("DELETE FROM daily_activity WHERE chat_id = %s AND user_id = %s AND activity_date = %s", (test_chat_id, test_user_id, today))
    
    await conn.close()


@pytest.mark.asyncio
async def test_pg_currency_repo():
    config = get_config()
    conn = await psycopg.AsyncConnection.connect(config.postgres_url)
    
    repo = PgCurrencyRepository(conn)
    
    from app.core.models import CurrencyRate
    from datetime import date
    
    rate = CurrencyRate(
        base_currency="USD",
        target_currency="EUR",
        rate_date=date.today(),
        rate=0.85,
    )
    
    await repo.store_rate(rate)
    
    # Test get_rate
    retrieved = await repo.get_rate("USD", "EUR", date.today())
    assert retrieved is not None
    from decimal import Decimal
    assert retrieved.rate == Decimal('0.85')
    
    # Clean up
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM currency_rates WHERE base_currency = %s AND target_currency = %s AND rate_date = %s", ("USD", "EUR", date.today()))
    
    await conn.close()


@pytest.mark.asyncio
async def test_connection_string():
    config = get_config()
    # Test that postgres_url is set and connection works
    try:
        conn = await psycopg.AsyncConnection.connect(config.postgres_url)
        await conn.close()
        assert True
    except Exception:
        assert False, "Failed to connect to database with the configured URL"