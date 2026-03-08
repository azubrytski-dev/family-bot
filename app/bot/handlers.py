from __future__ import annotations

from datetime import datetime, timezone
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.core.config import AppConfig
from app.core.services.activity_service import ActivityService
from app.core.services.ai_service import AiService
from app.core.services.chat_service import ChatRegistryService
from app.core.services.info_service import InfoService


def setup_handlers(
    dp: Dispatcher,
    bot: Bot,
    config: AppConfig,
    activity_service: ActivityService,
    ai_service: AiService,
    chat_registry: ChatRegistryService,
    info_service: InfoService,
) -> None:
    logger = logging.getLogger(__name__)
    target_chat_id = config.target_chat_id

    def is_allowed_chat(chat_id: int) -> bool:
        # If TARGET_CHAT_ID is not set, allow any chat.
        return target_chat_id is None or chat_id == target_chat_id

    async def _record_chat(message: Message) -> None:
        title = message.chat.title or getattr(message.chat, "full_name", None)
        chat_type = getattr(message.chat, "type", None)
        chat_type_str = getattr(chat_type, "value", str(chat_type)) if chat_type is not None else "unknown"
        await chat_registry.record_chat_seen(
            chat_id=message.chat.id,
            title=title,
            chat_type=chat_type_str,
        )

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        await _record_chat(message)
        if not is_allowed_chat(message.chat.id):
            return
        await message.answer(
            "Привет, семья! Я ваш бот-помощник. "
            "Буду напоминать о себе, делиться новостями и отвечать на упоминания 🙂"
        )

    @dp.message(Command("info"))
    async def info(message: Message) -> None:
        await _record_chat(message)
        if not is_allowed_chat(message.chat.id):
            return
        summary = await info_service.build_summary()
        await message.answer(summary)

    @dp.message(Command("activate"))
    async def activate(message: Message) -> None:
        logger.info(f"Activating chat {message.chat.id}")
        await _record_chat(message)
        if not is_allowed_chat(message.chat.id):
            return
        # Register the chat and the sender as a member
        if message.from_user is not None:
            now = datetime.now(timezone.utc)
            logger.info(f"Recording activation for user {message.from_user.id}")
            await activity_service.record_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                message_ts=now,
                username=message.from_user.username,
                display_name=message.from_user.full_name,
            )
        await message.answer("Чат активирован! Теперь я буду отслеживать активность.")

    @dp.message()
    async def handle_message(message: Message) -> None:
        logger.info(f"Handling message in chat {message.chat.id}, allowed: {is_allowed_chat(message.chat.id)}")
        await _record_chat(message)

        if not is_allowed_chat(message.chat.id):
            return

        if message.from_user is not None:
            now = datetime.now(timezone.utc)
            logger.info(f"Recording message for user {message.from_user.id}")
            await activity_service.record_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                message_ts=now,
                username=message.from_user.username,
                display_name=message.from_user.full_name,
            )

        text = message.text or message.caption or ""
        if not text:
            return

        if message.entities:
            bot_username = (await bot.me()).username
            mentioned = any(
                e.type == "mention" and f"@{bot_username}" in text[e.offset : e.offset + e.length]
                for e in message.entities
            )
            if mentioned:
                reply = await ai_service.reply_to_mention(text)
                await message.reply(reply)

