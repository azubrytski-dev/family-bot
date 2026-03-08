from __future__ import annotations

from datetime import date, datetime

import psycopg
from psycopg.rows import dict_row

from app.core.models import ChatRecord, CurrencyRate, NewsItem, NewsSource, WeatherSnapshot
from app.core.services.activity_service import ActivityRepository
from app.storage.repo import (
    ChatMembersRepository,
    ChatRegistryRepository,
    CurrencyRepository,
    DailyActivityRepository,
    NewsRepository,
    WeatherRepository,
)


class PgChatMembersRepository(ChatMembersRepository):
    def __init__(self, conn: psycopg.AsyncConnection) -> None:
        self._conn = conn

    async def ensure_member(
        self,
        chat_id: int,
        user_id: int,
        username: str | None,
        display_name: str | None,
    ) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO chat_members (chat_id, user_id, username, display_name, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (chat_id, user_id)
                DO UPDATE SET username = EXCLUDED.username,
                              display_name = EXCLUDED.display_name,
                              is_active = TRUE
                """,
                (chat_id, user_id, username, display_name),
            )

    async def get_member_ids(self, chat_id: int) -> list[int]:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT user_id FROM chat_members WHERE chat_id = %s AND is_active = TRUE",
                (chat_id,),
            )
            rows = await cur.fetchall()
        return [int(r["user_id"]) for r in rows]


class PgDailyActivityRepository(DailyActivityRepository):
    def __init__(self, conn: psycopg.AsyncConnection) -> None:
        self._conn = conn

    async def increment_message_count(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
    ) -> None:
        async with self._conn.cursor() as cur:
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

    async def get_activity_for_date(self, chat_id: int, day: date) -> dict[int, int]:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT user_id, message_count
                FROM daily_activity
                WHERE chat_id = %s AND activity_date = %s
                """,
                (chat_id, day),
            )
            rows = await cur.fetchall()
        return {int(r["user_id"]): int(r["message_count"]) for r in rows}


class PgActivityRepository(ActivityRepository):
    """
    Lightweight last-activity tracking using chat_members_activity table.

    One row per (chat_id, user_id) with last message timestamps.
    """

    def __init__(self, conn: psycopg.AsyncConnection) -> None:
        self._conn = conn

    async def increment_message_count(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
        username: str | None,
        display_name: str | None,
    ) -> None:
        async with self._conn.cursor() as cur:
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

    async def get_today_activity(self, chat_id: int, day: date) -> dict[int, int]:
        async with self._conn.cursor(row_factory=dict_row) as cur:
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
        async with self._conn.cursor(row_factory=dict_row) as cur:
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


class PgWeatherRepository(WeatherRepository):
    def __init__(self, conn: psycopg.AsyncConnection) -> None:
        self._conn = conn

    async def store_snapshot(self, snapshot: WeatherSnapshot) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO weather_snapshots (
                    city,
                    snapshot_date,
                    temperature,
                    feels_like,
                    condition,
                    wind_speed,
                    raw_payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (city, snapshot_date)
                DO UPDATE SET temperature = EXCLUDED.temperature,
                              feels_like = EXCLUDED.feels_like,
                              condition = EXCLUDED.condition,
                              wind_speed = EXCLUDED.wind_speed,
                              raw_payload = EXCLUDED.raw_payload
                """,
                (
                    snapshot.city,
                    snapshot.snapshot_date,
                    snapshot.temperature,
                    snapshot.feels_like,
                    snapshot.condition,
                    snapshot.wind_speed,
                    snapshot.raw_payload,
                ),
            )

    async def get_snapshot(self, city: str, day: date) -> WeatherSnapshot | None:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT city,
                       snapshot_date,
                       temperature,
                       feels_like,
                       condition,
                       wind_speed,
                       raw_payload
                FROM weather_snapshots
                WHERE city = %s AND snapshot_date = %s
                """,
                (city, day),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return WeatherSnapshot(
            city=row["city"],
            snapshot_date=row["snapshot_date"],
            temperature=row["temperature"],
            feels_like=row.get("feels_like"),
            condition=row["condition"],
            wind_speed=row.get("wind_speed"),
            raw_payload=row["raw_payload"],
        )

    async def get_latest_snapshot_up_to(self, city: str, day: date) -> WeatherSnapshot | None:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT city,
                       snapshot_date,
                       temperature,
                       feels_like,
                       condition,
                       wind_speed,
                       raw_payload
                FROM weather_snapshots
                WHERE city = %s AND snapshot_date <= %s
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                (city, day),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return WeatherSnapshot(
            city=row["city"],
            snapshot_date=row["snapshot_date"],
            temperature=row["temperature"],
            feels_like=row.get("feels_like"),
            condition=row["condition"],
            wind_speed=row.get("wind_speed"),
            raw_payload=row["raw_payload"],
        )


class PgCurrencyRepository(CurrencyRepository):
    def __init__(self, conn: psycopg.AsyncConnection) -> None:
        self._conn = conn

    async def store_rate(self, rate: CurrencyRate) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO currency_rates (base_currency, target_currency, rate_date, rate)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (base_currency, target_currency, rate_date)
                DO UPDATE SET rate = EXCLUDED.rate
                """,
                (rate.base_currency, rate.target_currency, rate.rate_date, rate.rate),
            )

    async def get_rate(
        self,
        base_currency: str,
        target_currency: str,
        day: date,
    ) -> CurrencyRate | None:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT base_currency, target_currency, rate_date, rate
                FROM currency_rates
                WHERE base_currency = %s AND target_currency = %s AND rate_date = %s
                """,
                (base_currency, target_currency, day),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return CurrencyRate(
            base_currency=row["base_currency"],
            target_currency=row["target_currency"],
            rate_date=row["rate_date"],
            rate=row["rate"],
        )

    async def get_latest_rate_up_to(
        self,
        base_currency: str,
        target_currency: str,
        day: date,
    ) -> CurrencyRate | None:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT base_currency, target_currency, rate_date, rate
                FROM currency_rates
                WHERE base_currency = %s
                  AND target_currency = %s
                  AND rate_date <= %s
                ORDER BY rate_date DESC
                LIMIT 1
                """,
                (base_currency, target_currency, day),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return CurrencyRate(
            base_currency=row["base_currency"],
            target_currency=row["target_currency"],
            rate_date=row["rate_date"],
            rate=row["rate"],
        )


class PgNewsRepository(NewsRepository):
    def __init__(self, conn: psycopg.AsyncConnection) -> None:
        self._conn = conn

    async def list_sources(self) -> list[NewsSource]:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, name, country, category, url, enabled FROM news_sources WHERE enabled = TRUE"
            )
            rows = await cur.fetchall()
        return [
            NewsSource(
                id=row["id"],
                name=row["name"],
                country=row["country"],
                category=row["category"],
                url=row["url"],
                enabled=row["enabled"],
            )
            for row in rows
        ]


class PgChatRegistryRepository(ChatRegistryRepository):
    def __init__(self, conn: psycopg.AsyncConnection) -> None:
        self._conn = conn

    async def upsert_chat(
        self,
        chat_id: int,
        title: str | None,
        chat_type: str,
    ) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO chats (chat_id, title, chat_type, is_active, last_seen_at)
                VALUES (%s, %s, %s, TRUE, NOW())
                ON CONFLICT (chat_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    chat_type = EXCLUDED.chat_type,
                    is_active = TRUE,
                    last_seen_at = NOW()
                """,
                (chat_id, title, chat_type),
            )

    async def list_active_chats(self) -> list[ChatRecord]:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT chat_id, title, chat_type, is_active, last_seen_at, last_greeting_at
                FROM chats
                WHERE is_active = TRUE
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
                last_seen_at=row["last_seen_at"],
                last_greeting_at=row["last_greeting_at"],
            )
            for row in rows
        ]

    async def mark_inactive(self, chat_id: int) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE chats
                SET is_active = FALSE
                WHERE chat_id = %s
                """,
                (chat_id,),
            )

    async def update_last_greeting(self, chat_id: int) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE chats
                SET last_greeting_at = NOW()
                WHERE chat_id = %s
                """,
                (chat_id,),
            )

    async def upsert_items(self, items: list[NewsItem]) -> None:
        if not items:
            return
        async with self._conn.cursor() as cur:
            for item in items:
                await cur.execute(
                    """
                    INSERT INTO news_items (source_id, title, url, published_at, content_hash, raw_payload)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_id, content_hash)
                    DO NOTHING
                    """,
                    (
                        item.source_id,
                        item.title,
                        item.url,
                        item.published_at,
                        item.content_hash,
                        item.raw_payload,
                    ),
                )

    async def list_items_for_day(
        self,
        category: str,
        day: date,
    ) -> list[NewsItem]:
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT ni.id,
                       ni.source_id,
                       ni.title,
                       ni.url,
                       ni.published_at,
                       ni.content_hash,
                       ni.raw_payload
                FROM news_items ni
                JOIN news_sources ns ON ns.id = ni.source_id
                WHERE ns.category = %s
                  AND ni.published_at::date = %s
                """,
                (category, day),
            )
            rows = await cur.fetchall()
        return [
            NewsItem(
                id=row["id"],
                source_id=row["source_id"],
                title=row["title"],
                url=row["url"],
                published_at=row["published_at"],
                content_hash=row["content_hash"],
                raw_payload=row["raw_payload"],
            )
            for row in rows
        ]

