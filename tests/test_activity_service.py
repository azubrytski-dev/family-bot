from datetime import date, datetime, timezone

import pytest

from app.core.services.activity_service import ActivityService


class InMemoryRepo:
    def __init__(self) -> None:
        self.activity: dict[tuple[int, int, date], int] = {}
        self.members: set[tuple[int, int]] = set()

    async def increment_message_count(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
        username: str | None,
        display_name: str | None,
    ) -> None:
        day = message_ts.date()
        self.members.add((chat_id, user_id))
        key = (chat_id, user_id, day)
        self.activity[key] = self.activity.get(key, 0) + 1

    async def get_today_activity(self, chat_id: int, day: date) -> dict[int, int]:
        result: dict[int, int] = {}
        for (c_id, u_id, d), count in self.activity.items():
            if c_id == chat_id and d == day:
                result[u_id] = count
        return result

    async def get_chat_members(self, chat_id: int):
        return [u_id for (c_id, u_id) in self.members if c_id == chat_id]


@pytest.mark.asyncio
async def test_inactive_users():
    repo = InMemoryRepo()
    service = ActivityService(repo)

    chat_id = 1
    today = date.today()
    ts = datetime.now(timezone.utc)

    await service.record_message(chat_id, 100, ts, "user100", "User 100")
    await service.record_message(chat_id, 101, ts, "user101", "User 101")

    repo.members.add((chat_id, 100))
    repo.members.add((chat_id, 101))
    repo.members.add((chat_id, 102))

    inactive = await service.get_inactive_users(chat_id, today)
    assert 102 in inactive
    assert 100 not in inactive
    assert 101 not in inactive

