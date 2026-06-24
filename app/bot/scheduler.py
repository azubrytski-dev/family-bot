from __future__ import annotations

from datetime import date, datetime, timezone
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone as tz

from app.bot.formatting import format_activity_summary, format_good_morning, format_good_night
from app.core.config import AppConfig
from app.core.services.activity_service import ActivityService
from app.core.services.ai_service import AiService
from app.core.services.session_memory_service import SessionMemoryService
from app.core.services.weather_service import WeatherService
from app.storage.repo import SchedulerJobRepository


SUPPORTED_JOB_TYPES = {"good_morning", "good_night_and_activity", "weather_morning", "weather_alert_check"}


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

    if job_type == "good_morning":
        fallback_message = format_good_morning()
        if ai_service is None or session_memory_service is None:
            await _send_message(fallback_message)
            return
        try:
            if use_test_morning_context:
                morning_context = await session_memory_service.get_test_morning_summaries(
                    chat_id=chat_id,
                    as_of_utc=now_utc or datetime.now(timezone.utc),
                )
            else:
                morning_context = await session_memory_service.get_yesterday_completed_summaries(
                    chat_id=chat_id,
                    as_of_utc=now_utc or datetime.now(timezone.utc),
                )
            if not morning_context.summaries:
                await _send_message(fallback_message)
                return
            greeting = await ai_service.generate_morning_greeting(
                summary_date=morning_context.local_date,
                summaries=morning_context.summaries,
            )
            await _send_message(greeting)
        except Exception:
            logging.getLogger("scheduler").exception(
                "Falling back to static morning message for chat %s after summary-aware generation failed.",
                chat_id,
            )
            await _send_message(fallback_message)
        return

    if job_type == "weather_morning":
        await _send_message(await weather_service.build_morning_forecast_summary())
        return

    if job_type == "weather_alert_check":
        alerts = await weather_service.build_severe_weather_alerts()
        for alert in alerts:
            await _send_message(alert)
        return

    if job_type != "good_night_and_activity":
        raise ValueError(f"Unsupported scheduler job type: {job_type}")

    await _send_message(format_good_night())
    if not config.enable_activity_tracking:
        return
    today = activity_service.local_date_for(now_utc)
    inactive_labels = await activity_service.get_inactive_user_labels(chat_id, today)
    summary = format_activity_summary(today, inactive_labels)
    await _send_message(summary)


async def setup_scheduler(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    config: AppConfig,
    activity_service: ActivityService,
    weather_service: WeatherService,
    ai_service: AiService,
    session_memory_service: SessionMemoryService,
    scheduler_job_repo: SchedulerJobRepository,
) -> None:
    logger = logging.getLogger("scheduler")

    if not config.enable_scheduler:
        logger.info("Scheduled jobs disabled via ENABLE_SCHEDULER.")
        return

    jobs = list(await scheduler_job_repo.list_enabled_jobs())
    if not jobs:
        logger.warning("No enabled scheduler jobs found in database; scheduler will stay idle.")
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
