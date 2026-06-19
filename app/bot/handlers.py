from __future__ import annotations

from datetime import datetime, timezone
import logging

from aiogram import Dispatcher
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandStart
from aiogram.types import ChatMemberUpdated, Message

from app.core.config import AppConfig
from app.core.services.activity_service import ActivityService
from app.core.services.ai_service import AiService
from app.core.services.chat_service import ChatRegistryService


def _message_text(message: Message) -> str:
    return (message.text or message.caption or "").strip()


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
    return f"Автор: {author}\nСообщение: {_message_text(message)}"


def _is_active_bot_status(status: str | ChatMemberStatus) -> bool:
    status_value = status.value if isinstance(status, ChatMemberStatus) else str(status)
    return status_value in {
        "member",
        "administrator",
        "creator",
        "restricted",
    }


def setup_handlers(
    dp: Dispatcher,
    config: AppConfig,
    activity_service: ActivityService,
    ai_service: AiService,
    chat_registry: ChatRegistryService,
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

        context = _build_ai_context(message)
        reply = await ai_service.reply_to_mention(context)
        await message.answer(reply)
