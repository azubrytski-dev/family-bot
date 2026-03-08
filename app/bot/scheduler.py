from __future__ import annotations

from datetime import date, datetime
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone as tz

from app.bot.formatting import format_activity_summary, format_good_morning, format_good_night
from app.core.config import AppConfig
from app.core.services.activity_service import ActivityService


def setup_scheduler(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    config: AppConfig,
    activity_service: ActivityService,
) -> None:
    if config.target_chat_id is None:
        logging.getLogger("scheduler").warning(
            "TARGET_CHAT_ID is not set; scheduled messages are disabled."
        )
        return

    chat_id = config.target_chat_id
    minsk_tz = tz(config.tz_name)

    async def send_good_morning() -> None:
        await bot.send_message(chat_id, format_good_morning())

    async def send_good_night_and_activity() -> None:
        today = date.today()
        inactive_ids = await activity_service.get_inactive_users(chat_id, today)
        # For now we just render user IDs; later we can resolve to @usernames.
        inactive_labels = [f"id:{user_id}" for user_id in inactive_ids]
        summary = format_activity_summary(today, inactive_labels)
        await bot.send_message(chat_id, format_good_night())
        await bot.send_message(chat_id, summary)

    scheduler.add_job(
        send_good_morning,
        CronTrigger(hour=8, minute=0, timezone=minsk_tz),
        name="good_morning",
    )
    scheduler.add_job(
        send_good_night_and_activity,
        CronTrigger(hour=23, minute=0, timezone=minsk_tz),
        name="good_night_and_activity",
    )

