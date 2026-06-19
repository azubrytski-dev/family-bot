from __future__ import annotations

from datetime import date
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone as tz

from app.bot.formatting import format_activity_summary, format_good_morning, format_good_night
from app.core.config import AppConfig
from app.core.services.activity_service import ActivityService
from app.storage.repo import SchedulerJobRepository


SUPPORTED_JOB_TYPES = {"good_morning", "good_night_and_activity"}


async def setup_scheduler(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    config: AppConfig,
    activity_service: ActivityService,
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

    async def send_good_morning(chat_id: int) -> None:
        await bot.send_message(chat_id, format_good_morning())

    async def send_good_night_and_activity(chat_id: int) -> None:
        await bot.send_message(chat_id, format_good_night())
        if not config.enable_activity_tracking:
            return
        today = date.today()
        inactive_ids = await activity_service.get_inactive_users(chat_id, today)
        # For now we just render user IDs; later we can resolve to @usernames.
        inactive_labels = [f"id:{user_id}" for user_id in inactive_ids]
        summary = format_activity_summary(today, inactive_labels)
        await bot.send_message(chat_id, summary)

    for job in jobs:
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

        if job.job_type == "good_morning":
            scheduler.add_job(
                send_good_morning,
                trigger,
                args=[job.chat_id],
                name=job.job_key,
            )
            continue

        scheduler.add_job(
            send_good_night_and_activity,
            trigger,
            args=[job.chat_id],
            name=job.job_key,
        )
