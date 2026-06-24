from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TZ_NAME = "Europe/Minsk"


class ActivityRepository(Protocol):
    async def increment_message_count(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
        activity_date: date,
        username: str | None,
        display_name: str | None,
    ) -> None: ...

    async def get_today_activity(self, chat_id: int, day: date) -> dict[int, int]: ...

    async def get_chat_members(self, chat_id: int) -> Iterable[int]: ...

    async def get_chat_member_labels(self, chat_id: int) -> dict[int, str]: ...


class ActivityService:
    def __init__(self, repo: ActivityRepository, tz_name: str = DEFAULT_TZ_NAME) -> None:
        self._repo = repo
        self._tz = _resolve_timezone(tz_name)

    async def record_message(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
        username: str | None,
        display_name: str | None,
    ) -> None:
        normalized_ts = _normalize_utc(message_ts)
        await self._repo.increment_message_count(
            chat_id=chat_id,
            user_id=user_id,
            message_ts=normalized_ts,
            activity_date=self._local_date(normalized_ts),
            username=username,
            display_name=display_name,
        )

    async def get_inactive_users(self, chat_id: int, day: date) -> list[int]:
        activity = await self._repo.get_today_activity(chat_id, day)
        members = set(await self._repo.get_chat_members(chat_id))
        active_users = {user_id for user_id, count in activity.items() if count > 0}
        inactive = sorted(members - active_users)
        return list(inactive)

    async def get_inactive_user_labels(self, chat_id: int, day: date) -> list[str]:
        inactive_user_ids = await self.get_inactive_users(chat_id, day)
        labels = await self._repo.get_chat_member_labels(chat_id)
        return [labels.get(user_id, f"id:{user_id}") for user_id in inactive_user_ids]

    def local_date_for(self, value: datetime | None = None) -> date:
        normalized = _normalize_utc(value or datetime.now(timezone.utc))
        return self._local_date(normalized)

    def _local_date(self, value: datetime) -> date:
        return value.astimezone(self._tz).date()


def _resolve_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TZ_NAME)


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
