from __future__ import annotations

from typing import TypedDict

import pytest

from app.bot.scheduler import execute_scheduler_job, setup_scheduler
from app.core.config import AppConfig
from app.core.models import SchedulerJob
from app.core.services.activity_service import ActivityService


class DummyBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append((chat_id, text))


class ScheduledJobRecord(TypedDict):
    func: object
    trigger: object
    args: list[object]
    name: str | None


class RecordingScheduler:
    def __init__(self) -> None:
        self.jobs: list[ScheduledJobRecord] = []

    def add_job(self, func, trigger, args=None, name=None):  # type: ignore[no-untyped-def]
        self.jobs.append({"func": func, "trigger": trigger, "args": list(args or []), "name": name})


class InMemorySchedulerJobRepo:
    def __init__(self, jobs: list[SchedulerJob]) -> None:
        self._jobs = jobs

    async def list_enabled_jobs(self) -> list[SchedulerJob]:
        return list(self._jobs)


class InMemoryActivityRepo:
    async def increment_message_count(self, chat_id, user_id, message_ts, username, display_name):  # type: ignore[no-untyped-def]
        return None

    async def get_today_activity(self, chat_id, day):  # type: ignore[no-untyped-def]
        return {}

    async def get_chat_members(self, chat_id):  # type: ignore[no-untyped-def]
        return []

    async def get_chat_member_labels(self, chat_id):  # type: ignore[no-untyped-def]
        return {}


def _make_config(monkeypatch) -> AppConfig:
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return AppConfig(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_setup_scheduler_loads_db_jobs(monkeypatch):
    cfg = _make_config(monkeypatch)
    scheduler = RecordingScheduler()
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    repo = InMemorySchedulerJobRepo(
        [
            SchedulerJob(
                job_key="good_morning",
                job_type="good_morning",
                cron_hour=8,
                cron_minute=0,
                timezone_name="Europe/Minsk",
                chat_id=321,
                enabled=True,
            ),
            SchedulerJob(
                job_key="night",
                job_type="good_night_and_activity",
                cron_hour=23,
                cron_minute=0,
                timezone_name="Europe/Minsk",
                chat_id=999,
                enabled=True,
            ),
        ]
    )

    await setup_scheduler(scheduler, bot, cfg, activity_service, repo)  # type: ignore[arg-type]

    assert [job["name"] for job in scheduler.jobs] == ["good_morning", "night"]
    assert scheduler.jobs[0]["args"][0] == "good_morning"
    assert scheduler.jobs[0]["args"][2] == 321
    assert scheduler.jobs[1]["args"][0] == "good_night_and_activity"
    assert scheduler.jobs[1]["args"][2] == 999


@pytest.mark.asyncio
async def test_setup_scheduler_skips_jobs_without_chat_id(monkeypatch):
    cfg = _make_config(monkeypatch)
    scheduler = RecordingScheduler()
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    repo = InMemorySchedulerJobRepo(
        [
            SchedulerJob(
                job_key="good_morning",
                job_type="good_morning",
                cron_hour=8,
                cron_minute=0,
                timezone_name="Europe/Minsk",
                chat_id=None,
                enabled=True,
            )
        ]
    )

    await setup_scheduler(scheduler, bot, cfg, activity_service, repo)  # type: ignore[arg-type]

    assert scheduler.jobs == []


@pytest.mark.asyncio
async def test_execute_scheduler_job_sends_morning_message(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]

    await execute_scheduler_job("good_morning", bot, 321, cfg, activity_service)  # type: ignore[arg-type]

    assert bot.sent_messages == [(321, "Доброе утро, зубры! ☕️ Желаю всем классного дня!")]


@pytest.mark.asyncio
async def test_execute_scheduler_job_uses_display_names_in_activity_summary(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()

    class InactiveLabelRepo(InMemoryActivityRepo):
        async def get_today_activity(self, chat_id, day):  # type: ignore[no-untyped-def]
            return {100: 1}

        async def get_chat_members(self, chat_id):  # type: ignore[no-untyped-def]
            return [100, 101]

        async def get_chat_member_labels(self, chat_id):  # type: ignore[no-untyped-def]
            return {100: "Active User", 101: "Inactive User"}

    activity_service = ActivityService(InactiveLabelRepo())  # type: ignore[arg-type]

    await execute_scheduler_job("good_night_and_activity", bot, 321, cfg, activity_service)  # type: ignore[arg-type]

    assert bot.sent_messages[0] == (321, "Спокойной ночи, зубры 😴 Пусть завтра будет ещё лучше, чем сегодня.")
    assert "Inactive User" in bot.sent_messages[1][1]
    assert "id:101" not in bot.sent_messages[1][1]
