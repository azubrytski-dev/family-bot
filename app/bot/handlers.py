from __future__ import annotations

from datetime import datetime, timezone
import logging

from aiogram import Dispatcher
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandStart
from aiogram.types import ChatMemberUpdated, Message

from app.bot.scheduler import execute_scheduler_job
from app.core.config import AppConfig
from app.core.services.activity_service import ActivityService
from app.core.services.ai_service import AiService
from app.core.services.chat_service import ChatRegistryService
from app.core.services.session_memory_service import SessionMemoryService
from app.core.services.weather_service import WeatherService


def _message_text(message: Message | None) -> str:
    if message is None:
        return ""
    return (message.text or message.caption or "").strip()


def _message_storage_text(message: Message | None) -> str:
    if message is None:
        return ""
    return (message.text or "").strip()


def _is_ai_trigger(
    message: Message,
    bot_username: str | None,
    bot_user_id: int | None,
) -> bool:
    text = _message_text(message)
    if not text:
        return False

    if bot_username and f"@{bot_username.lower()}" in text.lower():
        return True

    reply_from = getattr(getattr(message, "reply_to_message", None), "from_user", None)
    if bot_user_id is not None and reply_from is not None and reply_from.id == bot_user_id:
        return True

    return False


def _build_ai_context(message: Message) -> str:
    author = (
        getattr(message.from_user, "full_name", None)
        or getattr(message.from_user, "username", None)
        or "Unknown"
    )
    user_message = _message_text(message)
    reply_text = _message_text(getattr(message, "reply_to_message", None))

    if reply_text:
        return (
            f"Автор: {author}\n"
            f"bot_message: {reply_text}\n"
            f"user_reply: {user_message}"
        )

    return f"Автор: {author}\nСообщение: {user_message}"


async def _build_reply_context(
    message: Message,
    *,
    session_memory_service: SessionMemoryService | None,
) -> str:
    if session_memory_service is None:
        return _build_ai_context(message)

    author = (
        getattr(message.from_user, "full_name", None)
        or getattr(message.from_user, "username", None)
        or "Unknown"
    )
    message_ts = getattr(message, "date", None) or datetime.now(timezone.utc)
    return await session_memory_service.build_reply_context(
        chat_id=message.chat.id,
        author_name=author,
        message_text=_message_text(message),
        reply_to_message_text=_message_text(getattr(message, "reply_to_message", None)),
        as_of_utc=message_ts,
    )


def _is_reply_to_bot(message: Message, bot_user_id: int | None) -> bool:
    if bot_user_id is None:
        return False
    reply_from = getattr(getattr(message, "reply_to_message", None), "from_user", None)
    return reply_from is not None and reply_from.id == bot_user_id


def _is_active_bot_status(status: str | ChatMemberStatus) -> bool:
    status_value = status.value if isinstance(status, ChatMemberStatus) else str(status)
    return status_value in {
        "member",
        "administrator",
        "creator",
        "restricted",
    }


def _test_command_action(text: str) -> str | None:
    normalized = text.strip()
    if not normalized:
        return None

    command = normalized.split(maxsplit=1)[0].split("@", maxsplit=1)[0].lower()
    if command == "/test_morning":
        return "good_morning"
    if command == "/test_night":
        return "good_night_and_activity"
    if command == "/weather_test":
        return "weather_test"
    return None


async def _handle_test_command(
    *,
    action: str,
    message: Message,
    bot,
    config: AppConfig,
    activity_service: ActivityService,
    ai_service: AiService,
    weather_service: WeatherService,
    chat_registry: ChatRegistryService,
    session_memory_service: SessionMemoryService | None,
    bot_username: str | None,
    logger: logging.Logger,
) -> bool:
    if not await chat_registry.is_chat_test_allowed(message.chat.id):
        logger.info("Chat %s is approved but test commands are disabled.", message.chat.id)
        await message.answer("Тестовые команды для этого чата отключены.")
        return True

    if action == "weather_test":
        reply_text = await weather_service.build_morning_forecast_summary()
        sent_message = await message.answer(reply_text)
        if session_memory_service is not None:
            sent_message_id = getattr(sent_message, "message_id", None)
            if sent_message_id is not None:
                sent_message_ts = getattr(sent_message, "date", None) or datetime.now(timezone.utc)
                await session_memory_service.record_bot_reply(
                    chat_id=message.chat.id,
                    telegram_message_id=sent_message_id,
                    message_text=reply_text,
                    message_ts_utc=sent_message_ts,
                    bot_username=bot_username,
                )
        return True

    await execute_scheduler_job(
        job_type=action,
        bot=bot,
        chat_id=message.chat.id,
        config=config,
        activity_service=activity_service,
        weather_service=weather_service,
        ai_service=ai_service,
        session_memory_service=session_memory_service,
        track_bot_replies=True,
        bot_username=bot_username,
        use_test_morning_context=(action == "good_morning"),
    )
    return True


def setup_handlers(
    dp: Dispatcher,
    bot,
    config: AppConfig,
    activity_service: ActivityService,
    ai_service: AiService,
    weather_service: WeatherService,
    chat_registry: ChatRegistryService,
    session_memory_service: SessionMemoryService | None,
    bot_username: str | None,
    bot_user_id: int | None,
) -> None:
    logger = logging.getLogger(__name__)

    async def _record_chat(message: Message) -> None:
        title = message.chat.title or getattr(message.chat, "full_name", None)
        chat_type = getattr(message.chat, "type", None)
        chat_type_str = getattr(chat_type, "value", str(chat_type)) if chat_type is not None else "unknown"
        await chat_registry.record_chat_seen(
            chat_id=message.chat.id,
            title=title,
            chat_type=chat_type_str,
        )

    async def _record_membership_chat(update: ChatMemberUpdated) -> None:
        title = update.chat.title or getattr(update.chat, "full_name", None)
        chat_type = getattr(update.chat.type, "value", str(update.chat.type))
        await chat_registry.record_chat_seen(
            chat_id=update.chat.id,
            title=title,
            chat_type=chat_type,
        )

    @dp.my_chat_member()
    async def on_my_chat_member(update: ChatMemberUpdated) -> None:
        old_status = update.old_chat_member.status
        new_status = update.new_chat_member.status
        was_active = _is_active_bot_status(old_status)
        is_active = _is_active_bot_status(new_status)

        if not was_active and is_active:
            logger.info("Bot was added back to chat %s; resetting approval flow.", update.chat.id)
            await _record_membership_chat(update)
            return

        if was_active and not is_active:
            logger.info("Bot was removed from chat %s; marking chat inactive.", update.chat.id)
            await chat_registry.mark_chat_removed(update.chat.id)
            return

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        await _record_chat(message)
        # No longer sending a reply from the handler.

    @dp.message(Command("activate"))
    async def activate(message: Message) -> None:
        logger.info(f"Activating chat {message.chat.id}")
        await _record_chat(message)
        if not await chat_registry.is_chat_approved(message.chat.id):
            logger.info("Chat %s is pending approval; skipping activation handling.", message.chat.id)
            return
        if not config.enable_activity_tracking:
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

    @dp.message()
    async def handle_message(message: Message) -> None:
        logger.info("Handling message in chat %s", message.chat.id)
        await _record_chat(message)

        if not await chat_registry.is_chat_approved(message.chat.id):
            logger.info("Chat %s is pending approval; skipping bot interaction.", message.chat.id)
            return

        action = _test_command_action(_message_text(message))
        if action is not None:
            handled = await _handle_test_command(
                action=action,
                message=message,
                bot=bot,
                config=config,
                activity_service=activity_service,
                ai_service=ai_service,
                weather_service=weather_service,
                chat_registry=chat_registry,
                session_memory_service=session_memory_service,
                bot_username=bot_username,
                logger=logger,
            )
            if handled:
                return

        if session_memory_service is not None and message.from_user is not None:
            raw_text = _message_storage_text(message)
            if raw_text:
                message_ts = getattr(message, "date", None) or datetime.now(timezone.utc)
                await session_memory_service.record_message(
                    chat_id=message.chat.id,
                    telegram_message_id=message.message_id,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    display_name=message.from_user.full_name,
                    message_text=raw_text,
                    message_ts_utc=message_ts,
                    is_reply_to_bot=_is_reply_to_bot(message, bot_user_id),
                )

        if config.enable_activity_tracking and message.from_user is not None:
            now = datetime.now(timezone.utc)
            logger.info(f"Recording message for user {message.from_user.id}")
            await activity_service.record_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                message_ts=now,
                username=message.from_user.username,
                display_name=message.from_user.full_name,
            )

        if not _is_ai_trigger(message, bot_username=bot_username, bot_user_id=bot_user_id):
            return

        context = await _build_reply_context(
            message,
            session_memory_service=session_memory_service,
        )
        reply = await ai_service.reply_to_mention(context)
        sent_message = await message.answer(reply)
        if session_memory_service is not None:
            sent_message_id = getattr(sent_message, "message_id", None)
            if sent_message_id is not None:
                sent_message_ts = getattr(sent_message, "date", None) or datetime.now(timezone.utc)
                await session_memory_service.record_bot_reply(
                    chat_id=message.chat.id,
                    telegram_message_id=sent_message_id,
                    message_text=reply,
                    message_ts_utc=sent_message_ts,
                    bot_username=bot_username,
                )
