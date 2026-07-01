from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import httpx
import logging
from typing import Awaitable, Callable, Protocol, TypeVar

from aiogram import Bot
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pytz import timezone as tz

from app.bot.formatting import format_activity_summary, format_good_morning, format_good_night
from app.core.config import AppConfig
from app.core.services.activity_service import ActivityService
from app.core.services.ai_service import AiService
from app.core.services.session_memory_service import SessionMemoryService
from app.core.services.weather_service import WeatherService
from app.storage.repo import SchedulerJobRepository


SUPPORTED_JOB_TYPES = {"good_morning", "good_night_and_activity", "weather_morning", "weather_alert_check"}
SESSION_EXPIRY_JOB_NAME = "session_memory_expiry"
SESSION_EXPIRY_INTERVAL_MINUTES = 60
SCHEDULED_RETRY_ATTEMPTS = 3
_T = TypeVar("_T")


class JobScheduler(Protocol):
    def add_job(
        self,
        func: object,
        trigger: object,
        args: list[object] | None = None,
        name: str | None = None,
    ) -> None: ...


async def execute_scheduler_job(
    job_type: str,
    bot: Bot,
    chat_id: int,
    config: AppConfig,
    activity_service: ActivityService,
    weather_service: WeatherService,
    ai_service: AiService | None = None,
    session_memory_service: SessionMemoryService | None = None,
    now_utc: datetime | None = None,
    track_bot_replies: bool = False,
    bot_username: str | None = None,
    use_test_morning_context: bool = False,
) -> None:
    async def _send_message(text: str) -> None:
        sent_message = await bot.send_message(chat_id, text)
        if not track_bot_replies or session_memory_service is None:
            return
        sent_message_id = getattr(sent_message, "message_id", None)
        if sent_message_id is None:
            return
        sent_message_ts = getattr(sent_message, "date", None) or (now_utc or datetime.now(timezone.utc))
        await session_memory_service.record_bot_reply(
            chat_id=chat_id,
            telegram_message_id=sent_message_id,
            message_text=text,
            message_ts_utc=sent_message_ts,
            bot_username=bot_username,
        )

    logger = logging.getLogger("scheduler")

    if job_type == "good_morning":
        fallback_message = format_good_morning()
        if ai_service is None or session_memory_service is None:
            await _send_message(fallback_message)
            return
        try:
            if use_test_morning_context:
                morning_context = await _run_scheduled_with_retries(
                    operation_name="get_test_morning_summaries",
                    job_type=job_type,
                    chat_id=chat_id,
                    logger=logger,
                    factory=lambda: session_memory_service.get_test_morning_summaries(
                        chat_id=chat_id,
                        as_of_utc=now_utc or datetime.now(timezone.utc),
                    ),
                )
            else:
                morning_context = await _run_scheduled_with_retries(
                    operation_name="get_yesterday_completed_summaries",
                    job_type=job_type,
                    chat_id=chat_id,
                    logger=logger,
                    factory=lambda: session_memory_service.get_yesterday_completed_summaries(
                        chat_id=chat_id,
                        as_of_utc=now_utc or datetime.now(timezone.utc),
                    ),
                )
            if not morning_context.summaries:
                await _send_message(fallback_message)
                return
            greeting = await _run_scheduled_with_retries(
                operation_name="generate_morning_greeting",
                job_type=job_type,
                chat_id=chat_id,
                logger=logger,
                factory=lambda: ai_service.generate_morning_greeting(
                    summary_date=morning_context.local_date,
                    summaries=morning_context.summaries,
                ),
            )
            await _send_message(greeting)
        except Exception:
            logger.exception(
                "Falling back to static morning message for chat %s after summary-aware generation failed.",
                chat_id,
            )
            await _send_message(fallback_message)
        return

    if job_type == "weather_morning":
        summary = await _run_scheduled_with_retries(
            operation_name="build_morning_forecast_summary",
            job_type=job_type,
            chat_id=chat_id,
            logger=logger,
            factory=weather_service.build_morning_forecast_summary,
        )
        await _send_message(summary)
        return

    if job_type == "weather_alert_check":
        alerts = await _run_scheduled_with_retries(
            operation_name="build_severe_weather_alerts",
            job_type=job_type,
            chat_id=chat_id,
            logger=logger,
            factory=weather_service.build_severe_weather_alerts,
        )
        for alert in alerts:
            await _send_message(alert)
        return

    if job_type != "good_night_and_activity":
        raise ValueError(f"Unsupported scheduler job type: {job_type}")

    fallback_message = format_good_night()
    if ai_service is None or session_memory_service is None:
        await _send_message(fallback_message)
    else:
        try:
            evening_context = await _run_scheduled_with_retries(
                operation_name="get_evening_summaries",
                job_type=job_type,
                chat_id=chat_id,
                logger=logger,
                factory=lambda: session_memory_service.get_evening_summaries(
                    chat_id=chat_id,
                    as_of_utc=now_utc or datetime.now(timezone.utc),
                ),
            )
            if not evening_context.yesterday_summaries and not evening_context.today_summaries:
                await _send_message(fallback_message)
            else:
                greeting = await _run_scheduled_with_retries(
                    operation_name="generate_evening_greeting",
                    job_type=job_type,
                    chat_id=chat_id,
                    logger=logger,
                    factory=lambda: ai_service.generate_evening_greeting(
                        yesterday_date=evening_context.yesterday_date,
                        today_date=evening_context.today_date,
                        yesterday_summaries=evening_context.yesterday_summaries,
                        today_summaries=evening_context.today_summaries,
                    ),
                )
                await _send_message(greeting)
        except Exception:
            logger.exception(
                "Falling back to static evening message for chat %s after summary-aware generation failed.",
                chat_id,
            )
            await _send_message(fallback_message)
    if not config.enable_activity_tracking:
        return
    today = activity_service.local_date_for(now_utc)
    inactive_labels = await activity_service.get_inactive_user_labels(chat_id, today)
    summary = format_activity_summary(today, inactive_labels)
    await _send_message(summary)


async def execute_session_expiry_job(session_memory_service: SessionMemoryService) -> None:
    logger = logging.getLogger("scheduler")
    completed_sessions = await _run_scheduled_with_retries(
        operation_name="complete_expired_sessions",
        job_type=SESSION_EXPIRY_JOB_NAME,
        chat_id=None,
        logger=logger,
        factory=session_memory_service.complete_expired_sessions,
    )
    if completed_sessions:
        logger.info(
            "Completed %s expired chat session(s) during housekeeping run.",
            len(completed_sessions),
        )


async def _run_scheduled_with_retries(
    *,
    operation_name: str,
    job_type: str,
    chat_id: int | None,
    logger: logging.Logger,
    factory: Callable[[], Awaitable[_T]],
) -> _T:
    for attempt in range(SCHEDULED_RETRY_ATTEMPTS):
        try:
            return await factory()
        except Exception as exc:
            logger.warning(
                "Scheduled operation failed.",
                extra={
                    "operation_name": operation_name,
                    "job_type": job_type,
                    "chat_id": chat_id,
                    "attempt": attempt + 1,
                    "max_attempts": SCHEDULED_RETRY_ATTEMPTS,
                },
                exc_info=True,
            )
            if attempt == SCHEDULED_RETRY_ATTEMPTS - 1:
                raise
            delay_seconds = 0.5 if isinstance(exc, httpx.ConnectTimeout) else 1.0
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Scheduled retry loop ended unexpectedly.")


async def setup_scheduler(
    scheduler: JobScheduler,
    bot: Bot,
    config: AppConfig,
    activity_service: ActivityService,
    weather_service: WeatherService,
    ai_service: AiService,
    session_memory_service: SessionMemoryService,
    scheduler_job_repo: SchedulerJobRepository,
    bot_username: str | None = None,
) -> None:
    logger = logging.getLogger("scheduler")

    if not config.enable_scheduler:
        logger.info("Scheduled jobs disabled via ENABLE_SCHEDULER.")
        return

    scheduler.add_job(
        execute_session_expiry_job,
        IntervalTrigger(minutes=SESSION_EXPIRY_INTERVAL_MINUTES, timezone=tz(config.tz_name)),
        args=[session_memory_service],
        name=SESSION_EXPIRY_JOB_NAME,
    )
    logger.info(
        "Registered internal scheduler job %s every %s minute(s) in timezone %s.",
        SESSION_EXPIRY_JOB_NAME,
        SESSION_EXPIRY_INTERVAL_MINUTES,
        config.tz_name,
    )

    jobs = list(await scheduler_job_repo.list_enabled_jobs())
    if not jobs:
        logger.warning("No enabled scheduler jobs found in database; only internal housekeeping jobs will run.")
        return

    logger.info("Loaded %s enabled scheduler job(s) from database.", len(jobs))

    for job in jobs:
        logger.info(
            (
                "Found scheduler job key=%s type=%s enabled=%s chat_id=%s "
                "schedule=%02d:%02d timezone=%s"
            ),
            job.job_key,
            job.job_type,
            job.enabled,
            job.chat_id,
            job.cron_hour,
            job.cron_minute,
            job.timezone_name,
        )

        if job.job_type not in SUPPORTED_JOB_TYPES:
            logger.warning("Skipping unsupported scheduler job type %s for %s.", job.job_type, job.job_key)
            continue

        if job.chat_id is None:
            logger.warning(
                "Skipping scheduler job %s because no chat_id is configured in DB.",
                job.job_key,
            )
            continue

        trigger = CronTrigger(
            hour=job.cron_hour,
            minute=job.cron_minute,
            timezone=tz(job.timezone_name),
        )

        scheduler.add_job(
            execute_scheduler_job,
            trigger,
            args=[
                job.job_type,
                bot,
                job.chat_id,
                config,
                activity_service,
                weather_service,
                ai_service,
                session_memory_service,
                None,
                True,
                bot_username,
            ],
            name=job.job_key,
        )
        logger.info(
            "Registered scheduler job key=%s type=%s chat_id=%s schedule=%02d:%02d timezone=%s.",
            job.job_key,
            job.job_type,
            job.chat_id,
            job.cron_hour,
            job.cron_minute,
            job.timezone_name,
        )
