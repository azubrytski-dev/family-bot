from datetime import date, datetime, timezone

import pytest

from app.core.services.activity_service import ActivityService


class InMemoryRepo:
    def __init__(self) -> None:
        self.activity: dict[tuple[int, int, date], int] = {}
        self.members: dict[tuple[int, int], dict[str, str | None]] = {}

    async def increment_message_count(
        self,
        chat_id: int,
        user_id: int,
        message_ts: datetime,
        username: str | None,
        display_name: str | None,
    ) -> None:
        day = message_ts.date()
        self.members[(chat_id, user_id)] = {
            "username": username,
            "display_name": display_name,
        }
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

    async def get_chat_member_labels(self, chat_id: int) -> dict[int, str]:
        labels: dict[int, str] = {}
        for (c_id, u_id), member in self.members.items():
            if c_id != chat_id:
                continue
            if member["display_name"]:
                labels[u_id] = str(member["display_name"])
                continue
            if member["username"]:
                labels[u_id] = f"@{member['username']}"
                continue
            labels[u_id] = f"id:{u_id}"
        return labels


@pytest.mark.asyncio
async def test_inactive_users():
    repo = InMemoryRepo()
    service = ActivityService(repo)

    chat_id = 1
    ts = datetime.now(timezone.utc)
    today = ts.date()

    await service.record_message(chat_id, 100, ts, "user100", "User 100")
    await service.record_message(chat_id, 101, ts, "user101", "User 101")

    repo.members[(chat_id, 100)] = {"username": "user100", "display_name": "User 100"}
    repo.members[(chat_id, 101)] = {"username": "user101", "display_name": "User 101"}
    repo.members[(chat_id, 102)] = {"username": "user102", "display_name": "User 102"}

    inactive = await service.get_inactive_users(chat_id, today)
    assert 102 in inactive
    assert 100 not in inactive
    assert 101 not in inactive


@pytest.mark.asyncio
async def test_inactive_user_labels_prefer_display_name():
    repo = InMemoryRepo()
    service = ActivityService(repo)

    chat_id = 1
    ts = datetime.now(timezone.utc)
    today = ts.date()

    await service.record_message(chat_id, 100, ts, "user100", "User 100")
    repo.members[(chat_id, 101)] = {"username": "user101", "display_name": "User 101"}
    repo.members[(chat_id, 102)] = {"username": None, "display_name": "User 102"}
    repo.members[(chat_id, 103)] = {"username": None, "display_name": None}

    inactive = await service.get_inactive_user_labels(chat_id, today)

    assert inactive == ["User 101", "User 102", "id:103"]
