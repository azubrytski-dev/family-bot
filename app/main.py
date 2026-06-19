from __future__ import annotations

import asyncio
import logging

import psycopg
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot.formatting import format_startup_greeting
from app.bot.handlers import setup_handlers
from app.bot.scheduler import setup_scheduler
from app.core.config import get_config
from app.core.services.activity_service import ActivityService
from app.core.services.ai_service import AiService
from app.core.services.chat_service import ChatRegistryService
from app.integrations.ai.openai_client import OpenAIClient
from app.storage.migrate import run_migrations
from app.storage.pg_repo import (
    PgActivityRepository,
    PgChatRegistryRepository,
    PgSchedulerJobRepository,
)


async def send_startup_greetings(bot: Bot, chat_registry_service: ChatRegistryService) -> None:
    logger = logging.getLogger("startup-greeting")
    greeting = format_startup_greeting()
    chats = list(await chat_registry_service.get_approved_chats())
    for chat in chats:
        try:
            await bot.send_message(chat.chat_id, greeting)
        except Exception:
            logger.exception("Failed to send startup greeting to chat %s.", chat.chat_id)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = get_config()

    if config.auto_run_migrations:
        logger = logging.getLogger("migrations")
        try:
            logger.info("Running database migrations on startup...")
            await run_migrations()
            logger.info("Database migrations completed.")
        except Exception:
            logger.exception("Failed to apply database migrations, aborting startup.")
            raise

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    bot_me = await bot.get_me()
    dp = Dispatcher(storage=MemoryStorage())

    conn = await psycopg.AsyncConnection.connect(config.postgres_url)

    # Repositories & services
    activity_repo = PgActivityRepository(conn)
    chat_registry_repo = PgChatRegistryRepository(conn)
    scheduler_job_repo = PgSchedulerJobRepository(conn)

    activity_service = ActivityService(repo=activity_repo)
    chat_registry_service = ChatRegistryService(repo=chat_registry_repo)

    openai_client = OpenAIClient(
        api_key=config.openai_api_key,
        model=config.openai_model,
    )

    ai_service = AiService(primary=openai_client)

    setup_handlers(
        dp,
        config,
        activity_service,
        ai_service,
        chat_registry_service,
        bot_me.username,
        bot_me.id,
    )

    await send_startup_greetings(bot, chat_registry_service)

    scheduler: AsyncIOScheduler | None = None
    if config.enable_scheduler:
        scheduler = AsyncIOScheduler()
        await setup_scheduler(scheduler, bot, config, activity_service, scheduler_job_repo)
        scheduler.start()

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        await bot.session.close()
        await openai_client.aclose()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
