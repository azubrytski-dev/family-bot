from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Protocol

from app.core.models import (
    ChatRecord,
    CurrencyRate,
    NewsItem,
    NewsItemIterable,
    NewsSource,
    WeatherSnapshot,
)


class ChatMembersRepository(Protocol):
    async def ensure_member(
        self,
        chat_id: int,
        user_id: int,
        username: str | None,
        display_name: str | None,
    ) -> None: ...

    async def get_member_ids(self, chat_id: int) -> Iterable[int]: ...


class DailyActivityRepository(Protocol):
    async def increment_message_count(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
    ) -> None: ...

    async def get_activity_for_date(self, chat_id: int, day: date) -> dict[int, int]: ...


class ChatRegistryRepository(Protocol):
    async def upsert_chat(
        self,
        chat_id: int,
        title: str | None,
        chat_type: str,
    ) -> None: ...

    async def list_active_chats(self) -> Iterable[ChatRecord]: ...

    async def mark_inactive(self, chat_id: int) -> None: ...

    async def update_last_greeting(self, chat_id: int) -> None: ...


class WeatherRepository(Protocol):
    async def store_snapshot(self, snapshot: WeatherSnapshot) -> None: ...

    async def get_snapshot(self, city: str, day: date) -> WeatherSnapshot | None: ...

    async def get_latest_snapshot_up_to(self, city: str, day: date) -> WeatherSnapshot | None: ...


class CurrencyRepository(Protocol):
    async def store_rate(self, rate: CurrencyRate) -> None: ...

    async def get_rate(
        self,
        base_currency: str,
        target_currency: str,
        day: date,
    ) -> CurrencyRate | None: ...

    async def get_latest_rate_up_to(
        self,
        base_currency: str,
        target_currency: str,
        day: date,
    ) -> CurrencyRate | None: ...


class NewsRepository(Protocol):
    async def list_sources(self) -> Iterable[NewsSource]: ...

    async def upsert_items(self, items: NewsItemIterable) -> None: ...

    async def list_items_for_day(
        self,
        category: str,
        day: date,
    ) -> Iterable[NewsItem]: ...

