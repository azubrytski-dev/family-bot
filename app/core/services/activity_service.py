from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Protocol


class ActivityRepository(Protocol):
    async def increment_message_count(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
        username: str | None,
        display_name: str | None,
    ) -> None: ...

    async def get_today_activity(self, chat_id: int, day: date) -> dict[int, int]: ...

    async def get_chat_members(self, chat_id: int) -> Iterable[int]: ...


class ActivityService:
    def __init__(self, repo: ActivityRepository) -> None:
        self._repo = repo

    async def record_message(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
        username: str | None,
        display_name: str | None,
    ) -> None:
        await self._repo.increment_message_count(
            chat_id=chat_id,
            user_id=user_id,
            message_ts=message_ts,
            username=username,
            display_name=display_name,
        )

    async def get_inactive_users(self, chat_id: int, day: date) -> list[int]:
        activity = await self._repo.get_today_activity(chat_id, day)
        members = set(await self._repo.get_chat_members(chat_id))
        active_users = {user_id for user_id, count in activity.items() if count > 0}
        inactive = sorted(members - active_users)
        return list(inactive)

