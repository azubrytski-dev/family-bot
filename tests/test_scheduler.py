from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from typing import TypedDict

import pytest

from app.bot.scheduler import execute_scheduler_job, setup_scheduler
from app.core.config import AppConfig
from app.core.models import SchedulerJob
from app.core.services.activity_service import ActivityService
from app.core.services.session_memory_service import MorningSummaryContext


class DummyBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append((chat_id, text))
        return type("SentMessage", (), {"message_id": 1000 + len(self.sent_messages), "date": datetime(2026, 6, 24, 5, 0, tzinfo=timezone.utc)})()


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
    async def increment_message_count(self, chat_id, user_id, message_ts, activity_date, username, display_name):  # type: ignore[no-untyped-def]
        return None

    async def get_today_activity(self, chat_id, day):  # type: ignore[no-untyped-def]
        return {}

    async def get_chat_members(self, chat_id):  # type: ignore[no-untyped-def]
        return []

    async def get_chat_member_labels(self, chat_id):  # type: ignore[no-untyped-def]
        return {}


class StubWeatherService:
    def __init__(self) -> None:
        self.morning_summary = "Погода утром готова."
        self.alerts = ["Погодное предупреждение для Minsk: 🌧️ Сильный дождь."]

    async def build_morning_forecast_summary(self) -> str:
        return self.morning_summary

    async def build_severe_weather_alerts(self) -> list[str]:
        return list(self.alerts)


class StubAiService:
    def __init__(self) -> None:
        self.morning_reply = "Доброе утро! Пусть день будет спокойным и хорошим."
        self.last_summary_date: date | None = None
        self.last_summaries: list[str] | None = None

    async def generate_morning_greeting(self, *, summary_date: date, summaries: list[str]) -> str:
        self.last_summary_date = summary_date
        self.last_summaries = list(summaries)
        return self.morning_reply


class FailingAiService(StubAiService):
    async def generate_morning_greeting(self, *, summary_date: date, summaries: list[str]) -> str:
        raise RuntimeError("ai failed")


class StubSessionMemoryService:
    def __init__(self, context: MorningSummaryContext | None = None) -> None:
        self.context = context or MorningSummaryContext(local_date=date(2026, 6, 23), summaries=[])
        self.calls: list[tuple[int, datetime | None]] = []
        self.test_calls: list[tuple[int, datetime | None]] = []
        self.bot_replies: list[dict[str, object]] = []

    async def get_yesterday_completed_summaries(
        self,
        *,
        chat_id: int,
        as_of_utc: datetime | None = None,
    ) -> MorningSummaryContext:
        self.calls.append((chat_id, as_of_utc))
        return self.context

    async def get_test_morning_summaries(
        self,
        *,
        chat_id: int,
        as_of_utc: datetime | None = None,
    ) -> MorningSummaryContext:
        self.test_calls.append((chat_id, as_of_utc))
        return self.context

    async def record_bot_reply(
        self,
        *,
        chat_id: int,
        telegram_message_id: int,
        message_text: str,
        message_ts_utc: datetime,
        bot_username: str | None,
    ) -> None:
        self.bot_replies.append(
            {
                "chat_id": chat_id,
                "telegram_message_id": telegram_message_id,
                "message_text": message_text,
                "message_ts_utc": message_ts_utc,
                "bot_username": bot_username,
            }
        )


def _make_config(monkeypatch) -> AppConfig:
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return AppConfig(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_setup_scheduler_loads_db_jobs(monkeypatch, caplog: pytest.LogCaptureFixture):
    cfg = _make_config(monkeypatch)
    scheduler = RecordingScheduler()
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    weather_service = StubWeatherService()
    ai_service = StubAiService()
    session_memory_service = StubSessionMemoryService()
    caplog.set_level(logging.INFO, logger="scheduler")
    repo = InMemorySchedulerJobRepo(
        [
            SchedulerJob(
                job_key="weather_morning",
                job_type="weather_morning",
                cron_hour=7,
                cron_minute=30,
                timezone_name="Europe/Minsk",
                chat_id=111,
                enabled=True,
            ),
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

    await setup_scheduler(
        scheduler,
        bot,
        cfg,
        activity_service,
        weather_service,
        ai_service,  # type: ignore[arg-type]
        session_memory_service,  # type: ignore[arg-type]
        repo,
    )

    assert [job["name"] for job in scheduler.jobs] == ["weather_morning", "good_morning", "night"]
    assert scheduler.jobs[0]["args"][0] == "weather_morning"
    assert scheduler.jobs[0]["args"][2] == 111
    assert scheduler.jobs[1]["args"][0] == "good_morning"
    assert scheduler.jobs[1]["args"][2] == 321
    assert scheduler.jobs[1]["args"][6] is ai_service
    assert scheduler.jobs[1]["args"][7] is session_memory_service
    assert scheduler.jobs[2]["args"][0] == "good_night_and_activity"
    assert scheduler.jobs[2]["args"][2] == 999
    assert "Loaded 3 enabled scheduler job(s) from database." in caplog.text
    assert "Found scheduler job key=weather_morning type=weather_morning enabled=True chat_id=111 schedule=07:30 timezone=Europe/Minsk" in caplog.text
    assert "Registered scheduler job key=weather_morning type=weather_morning chat_id=111 schedule=07:30 timezone=Europe/Minsk." in caplog.text


@pytest.mark.asyncio
async def test_setup_scheduler_skips_jobs_without_chat_id(
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
):
    cfg = _make_config(monkeypatch)
    scheduler = RecordingScheduler()
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    weather_service = StubWeatherService()
    ai_service = StubAiService()
    session_memory_service = StubSessionMemoryService()
    caplog.set_level(logging.INFO, logger="scheduler")
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

    await setup_scheduler(
        scheduler,
        bot,
        cfg,
        activity_service,
        weather_service,
        ai_service,  # type: ignore[arg-type]
        session_memory_service,  # type: ignore[arg-type]
        repo,
    )

    assert scheduler.jobs == []
    assert "Found scheduler job key=good_morning type=good_morning enabled=True chat_id=None schedule=08:00 timezone=Europe/Minsk" in caplog.text
    assert "Skipping scheduler job good_morning because no chat_id is configured in DB." in caplog.text


@pytest.mark.asyncio
async def test_execute_scheduler_job_sends_morning_message(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    weather_service = StubWeatherService()
    ai_service = StubAiService()
    session_memory_service = StubSessionMemoryService(
        MorningSummaryContext(
            local_date=date(2026, 6, 23),
            summaries=["Вчера обсуждали планы на день и прогулку с Малышом."],
        )
    )

    await execute_scheduler_job(
        "good_morning",
        bot,
        321,
        cfg,
        activity_service,
        weather_service,
        ai_service,  # type: ignore[arg-type]
        session_memory_service,  # type: ignore[arg-type]
        datetime(2026, 6, 24, 5, 0, tzinfo=timezone.utc),
    )

    assert bot.sent_messages == [(321, "Доброе утро! Пусть день будет спокойным и хорошим.")]
    assert ai_service.last_summary_date == date(2026, 6, 23)
    assert ai_service.last_summaries == ["Вчера обсуждали планы на день и прогулку с Малышом."]


@pytest.mark.asyncio
async def test_execute_scheduler_job_falls_back_for_morning_without_summaries(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    weather_service = StubWeatherService()

    await execute_scheduler_job(
        "good_morning",
        bot,
        321,
        cfg,
        activity_service,
        weather_service,
        StubAiService(),  # type: ignore[arg-type]
        StubSessionMemoryService(),  # type: ignore[arg-type]
        datetime(2026, 6, 24, 5, 0, tzinfo=timezone.utc),
    )

    assert bot.sent_messages == [(321, "Доброе утро, зубры! ☕️ Желаю всем классного дня!")]


@pytest.mark.asyncio
async def test_execute_scheduler_job_falls_back_for_morning_when_ai_fails(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    weather_service = StubWeatherService()
    session_memory_service = StubSessionMemoryService(
        MorningSummaryContext(local_date=date(2026, 6, 23), summaries=["Была насыщенная среда."])
    )

    await execute_scheduler_job(
        "good_morning",
        bot,
        321,
        cfg,
        activity_service,
        weather_service,
        FailingAiService(),  # type: ignore[arg-type]
        session_memory_service,  # type: ignore[arg-type]
        datetime(2026, 6, 24, 5, 0, tzinfo=timezone.utc),
    )

    assert bot.sent_messages == [(321, "Доброе утро, зубры! ☕️ Желаю всем классного дня!")]


@pytest.mark.asyncio
async def test_execute_scheduler_job_tracks_bot_replies_only_when_requested(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    weather_service = StubWeatherService()
    session_memory_service = StubSessionMemoryService()

    await execute_scheduler_job(
        "weather_morning",
        bot,
        321,
        cfg,
        activity_service,
        weather_service,
        session_memory_service=session_memory_service,  # type: ignore[arg-type]
        track_bot_replies=True,
        bot_username="family_bot",
    )

    assert bot.sent_messages == [(321, "Погода утром готова.")]
    assert session_memory_service.bot_replies == [
        {
            "chat_id": 321,
            "telegram_message_id": 1001,
            "message_text": "Погода утром готова.",
            "message_ts_utc": datetime(2026, 6, 24, 5, 0, tzinfo=timezone.utc),
            "bot_username": "family_bot",
        }
    ]


@pytest.mark.asyncio
async def test_execute_scheduler_job_uses_test_morning_context_when_requested(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    weather_service = StubWeatherService()
    ai_service = StubAiService()
    session_memory_service = StubSessionMemoryService(
        MorningSummaryContext(
            local_date=date(2026, 6, 24),
            summaries=["Сегодня уже обсуждали планы на завтрашнее утро."],
        )
    )
    now_utc = datetime(2026, 6, 24, 18, 0, tzinfo=timezone.utc)

    await execute_scheduler_job(
        "good_morning",
        bot,
        321,
        cfg,
        activity_service,
        weather_service,
        ai_service,  # type: ignore[arg-type]
        session_memory_service,  # type: ignore[arg-type]
        now_utc,
        False,
        None,
        True,
    )

    assert session_memory_service.calls == []
    assert session_memory_service.test_calls == [(321, now_utc)]
    assert ai_service.last_summary_date == date(2026, 6, 24)


@pytest.mark.asyncio
async def test_execute_scheduler_job_uses_display_names_in_activity_summary(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()
    weather_service = StubWeatherService()

    class InactiveLabelRepo(InMemoryActivityRepo):
        async def get_today_activity(self, chat_id, day):  # type: ignore[no-untyped-def]
            return {100: 1}

        async def get_chat_members(self, chat_id):  # type: ignore[no-untyped-def]
            return [100, 101]

        async def get_chat_member_labels(self, chat_id):  # type: ignore[no-untyped-def]
            return {100: "Active User", 101: "Inactive User"}

    activity_service = ActivityService(InactiveLabelRepo(), tz_name="Europe/Minsk")  # type: ignore[arg-type]

    await execute_scheduler_job(
        "good_night_and_activity",
        bot,
        321,
        cfg,
        activity_service,
        weather_service,
        now_utc=datetime(2026, 6, 23, 21, 30, tzinfo=timezone.utc),
    )  # type: ignore[arg-type]

    assert bot.sent_messages[0] == (321, "Спокойной ночи, зубры 😴 Пусть завтра будет ещё лучше, чем сегодня.")
    assert "24.06.2026" in bot.sent_messages[1][1]
    assert "Inactive User" in bot.sent_messages[1][1]
    assert "id:101" not in bot.sent_messages[1][1]


@pytest.mark.asyncio
async def test_execute_scheduler_job_sends_weather_morning_summary(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    weather_service = StubWeatherService()

    await execute_scheduler_job("weather_morning", bot, 321, cfg, activity_service, weather_service)  # type: ignore[arg-type]

    assert bot.sent_messages == [(321, "Погода утром готова.")]


@pytest.mark.asyncio
async def test_execute_scheduler_job_sends_severe_weather_alerts(monkeypatch):
    cfg = _make_config(monkeypatch)
    bot = DummyBot()
    activity_service = ActivityService(InMemoryActivityRepo())  # type: ignore[arg-type]
    weather_service = StubWeatherService()

    await execute_scheduler_job("weather_alert_check", bot, 321, cfg, activity_service, weather_service)  # type: ignore[arg-type]

    assert bot.sent_messages == [(321, "Погодное предупреждение для Minsk: 🌧️ Сильный дождь.")]
