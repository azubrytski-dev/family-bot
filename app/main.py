from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramMigrateToChat
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot.formatting import format_startup_greeting
from app.bot.handlers import setup_handlers
from app.bot.scheduler import setup_scheduler
from app.core.config import get_config
from app.core.services.activity_service import ActivityService
from app.core.services.ai_service import AiService
from app.core.services.chat_service import ChatRegistryService
from app.core.services.weather_service import WeatherService
from app.integrations.ai.openai_client import OpenAIClient
from app.integrations.weather.client import OpenMeteoWeatherClient
from app.storage.migrate import run_migrations
from app.storage.pg_repo import (
    PgActivityRepository,
    PgAppConfigRepository,
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
        except TelegramMigrateToChat as exc:
            new_chat_id = exc.migrate_to_chat_id
            logger.info(
                "Chat %s was upgraded to supergroup %s during startup greeting; migrating stored chat ID.",
                chat.chat_id,
                new_chat_id,
            )
            await chat_registry_service.migrate_chat(chat.chat_id, new_chat_id)
            try:
                await bot.send_message(new_chat_id, greeting)
            except Exception:
                logger.exception(
                    "Failed to send startup greeting to migrated chat %s (from %s).",
                    new_chat_id,
                    chat.chat_id,
                )
        except Exception:
            logger.exception("Failed to send startup greeting to chat %s.", chat.chat_id)


async def close_runtime_resources(
    bot: Bot,
    openai_client: OpenAIClient | None,
    weather_client: OpenMeteoWeatherClient | None,
    scheduler: AsyncIOScheduler | None,
) -> None:
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await bot.session.close()
    if openai_client is not None:
        await openai_client.aclose()
    if weather_client is not None:
        await weather_client.aclose()


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
    openai_client: OpenAIClient | None = None
    weather_client: OpenMeteoWeatherClient | None = None
    scheduler: AsyncIOScheduler | None = None
    try:
        bot_me = await bot.get_me()
        dp = Dispatcher(storage=MemoryStorage())

        # Repositories & services
        activity_repo = PgActivityRepository(config.postgres_url)
        app_config_repo = PgAppConfigRepository(config.postgres_url)
        chat_registry_repo = PgChatRegistryRepository(config.postgres_url)
        scheduler_job_repo = PgSchedulerJobRepository(config.postgres_url)

        activity_service = ActivityService(repo=activity_repo)
        chat_registry_service = ChatRegistryService(repo=chat_registry_repo)

        openai_client = OpenAIClient(
            api_key=config.openai_api_key,
            model=config.openai_model,
        )
        weather_client = OpenMeteoWeatherClient()

        ai_service = AiService(primary=openai_client)
        weather_service = WeatherService(
            config_repo=app_config_repo,
            weather_client=weather_client,
            ai_service=ai_service,
        )

        setup_handlers(
            dp,
            bot,
            config,
            activity_service,
            ai_service,
            weather_service,
            chat_registry_service,
            bot_me.username,
            bot_me.id,
        )

        await send_startup_greetings(bot, chat_registry_service)

        if config.enable_scheduler:
            scheduler = AsyncIOScheduler()
            await setup_scheduler(scheduler, bot, config, activity_service, scheduler_job_repo)
            scheduler.start()

        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await close_runtime_resources(
            bot=bot,
            openai_client=openai_client,
            weather_client=weather_client,
            scheduler=scheduler,
        )


if __name__ == "__main__":
    asyncio.run(main())
