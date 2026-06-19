from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.bot.scheduler import setup_scheduler
from app.core.config import AppConfig
from app.core.models import SchedulerJob
from app.core.services.activity_service import ActivityService


class DummyBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append((chat_id, text))


class RecordingScheduler:
    def __init__(self) -> None:
        self.jobs: list[dict[str, object]] = []

    def add_job(self, func, trigger, args=None, name=None):  # type: ignore[no-untyped-def]
        self.jobs.append({"func": func, "trigger": trigger, "args": args, "name": name})


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


def _make_config(monkeypatch, target_chat_id: str | None = "321") -> AppConfig:
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
    assert scheduler.jobs[0]["args"] == [321]
    assert scheduler.jobs[1]["args"] == [999]


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
