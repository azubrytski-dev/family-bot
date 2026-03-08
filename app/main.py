from __future__ import annotations

import asyncio
import logging

import psycopg
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot.handlers import setup_handlers
from app.bot.scheduler import setup_scheduler
from app.core.config import get_config
from app.core.services.activity_service import ActivityService
from app.core.services.ai_service import AiService
from app.core.services.chat_service import ChatRegistryService
from app.core.services.currency_service import CurrencyService
from app.core.services.info_service import InfoService
from app.core.services.weather_service import WeatherService
from app.integrations.ai.gemini_client import GeminiClient
from app.integrations.ai.openai_client import OpenAIClient
from app.integrations.rates.client import RatesApiClient
from app.integrations.weather.client import WeatherApiClient
from app.storage.migrate import run_migrations
from app.storage.pg_repo import (
    PgActivityRepository,
    PgChatRegistryRepository,
    PgCurrencyRepository,
    PgWeatherRepository,
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
    dp = Dispatcher(storage=MemoryStorage())

    conn = await psycopg.AsyncConnection.connect(config.postgres_url)

    # Repositories & services
    activity_repo = PgActivityRepository(conn)
    weather_repo = PgWeatherRepository(conn)
    currency_repo = PgCurrencyRepository(conn)
    chat_registry_repo = PgChatRegistryRepository(conn)

    activity_service = ActivityService(repo=activity_repo)
    chat_registry_service = ChatRegistryService(repo=chat_registry_repo)

    weather_client: WeatherApiClient | None = None
    if config.weather_api_key:
        weather_client = WeatherApiClient(
            api_key=config.weather_api_key,
            base_url=config.weather_api_base_url,
        )

    rates_client = RatesApiClient(base_url=config.rates_api_base_url)

    if weather_client is None:
        # Weather integration is optional; summary will show a fallback message.
        weather_service = WeatherService(config=config, repo=weather_repo, client=_NullWeatherClient())
    else:
        weather_service = WeatherService(config=config, repo=weather_repo, client=weather_client)

    currency_service = CurrencyService(repo=currency_repo, client=rates_client)
    info_service = InfoService(weather_service=weather_service, currency_service=currency_service)

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
        bot,
        config,
        activity_service,
        ai_service,
        chat_registry_service,
        info_service,
    )

    scheduler = AsyncIOScheduler()
    setup_scheduler(scheduler, bot, config, activity_service)
    scheduler.start()

    # Startup greeting to all active chats.
    await _send_startup_greetings(bot, chat_registry_service)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        if primary_ai:
            await primary_ai.aclose()
        if fallback_ai:
            await fallback_ai.aclose()
        if weather_client:
            await weather_client.aclose()
        await rates_client.aclose()
        await conn.close()


class _NullWeatherClient:
    """
    Fallback weather client used when no API key is configured.
    It always returns None, letting WeatherService rely on stored data only.
    """

    async def get_current(self, city: str):  # type: ignore[no-untyped-def]
        return None


async def _send_startup_greetings(
    bot: Bot,
    chat_registry: ChatRegistryService,
) -> None:
    logger = logging.getLogger("startup_greetings")
    greeting_text = "Бот запущен и готов помогать 👋"

    for chat in await chat_registry.get_active_chats():
        try:
            await bot.send_message(chat.chat_id, greeting_text)
            await chat_registry.mark_greeted(chat.chat_id)
        except (TelegramForbiddenError, TelegramBadRequest):
            logger.info("Chat %s is no longer available; marking inactive.", chat.chat_id)
            await chat_registry.mark_inactive(chat.chat_id)
        except Exception:
            logger.exception("Failed to send greeting to chat %s; continuing.", chat.chat_id)


if __name__ == "__main__":
    asyncio.run(main())

