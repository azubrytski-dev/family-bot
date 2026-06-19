from __future__ import annotations

import asyncio
import logging

import psycopg
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot.handlers import setup_handlers
from app.bot.scheduler import setup_scheduler
from app.core.config import get_config
from app.core.services.activity_service import ActivityService
from app.core.services.ai_service import AiService
from app.core.services.chat_service import ChatRegistryService
from app.integrations.ai.gemini_client import GeminiClient
from app.integrations.ai.openai_client import OpenAIClient
from app.storage.migrate import run_migrations
from app.storage.pg_repo import (
    PgActivityRepository,
    PgChatRegistryRepository,
    PgSchedulerJobRepository,
)


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

    # AI clients
    primary_ai: GeminiClient | None = None
    fallback_ai: OpenAIClient | None = None
    if config.gemini_api_key:
        primary_ai = GeminiClient(config.gemini_api_key)
    if config.openai_api_key:
        fallback_ai = OpenAIClient(config.openai_api_key)

    if primary_ai is None and fallback_ai is None:
        raise RuntimeError("At least one AI provider (Gemini or OpenAI) must be configured.")

    ai_service = AiService(
        primary=primary_ai or fallback_ai,
        fallback=fallback_ai if primary_ai else None,
    )

    setup_handlers(
        dp,
        config,
        activity_service,
        ai_service,
        chat_registry_service,
        bot_me.username,
        bot_me.id,
    )

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
        if primary_ai:
            await primary_ai.aclose()
        if fallback_ai:
            await fallback_ai.aclose()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
