from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable


@dataclass
class ChatMember:
    chat_id: int
    user_id: int
    username: str | None
    display_name: str | None
    is_active: bool


@dataclass
class DailyActivity:
    chat_id: int
    user_id: int
    activity_date: date
    message_count: int
    last_message_ts: datetime | None


@dataclass
class ChatRecord:
    chat_id: int
    title: str | None
    chat_type: str
    is_active: bool
    last_seen_at: datetime
    last_greeting_at: datetime | None


@dataclass
class ChatMemberActivity:
    chat_id: int
    user_id: int
    username: str | None
    display_name: str | None
    last_message_at: datetime | None
    last_message_date: date | None
    updated_at: datetime


@dataclass
class WeatherSnapshot:
    city: str
    snapshot_date: date
    temperature: float | None
    feels_like: float | None
    condition: str | None
    wind_speed: float | None
    raw_payload: dict[str, Any] | None


@dataclass
class CurrencyRate:
    base_currency: str
    target_currency: str
    rate_date: date
    rate: float


@dataclass
class NewsSource:
    id: int
    name: str
    country: str
    category: str
    url: str
    enabled: bool


@dataclass
class NewsItem:
    id: int
    source_id: int
    title: str
    url: str
    published_at: datetime
    content_hash: str
    raw_payload: dict[str, Any] | None


NewsItemIterable = Iterable[NewsItem]

