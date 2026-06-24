from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import cast

import pytest
from aiogram.types import Message

from app.bot.handlers import (
    _build_ai_context,
    _handle_test_command,
    _is_active_bot_status,
    _is_ai_trigger,
    _test_command_action,
)
from app.core.config import AppConfig
from app.core.services.session_memory_service import BOT_SESSION_USER_ID


class DummyWeatherService:
    def __init__(self, summary: str = "Погода готова.") -> None:
        self.summary = summary
        self.calls = 0

    async def build_morning_forecast_summary(self) -> str:
        self.calls += 1
        return self.summary


class DummyChatRegistry:
    def __init__(self, allow_test: bool) -> None:
        self.allow_test = allow_test

    async def is_chat_test_allowed(self, chat_id: int) -> bool:
        return self.allow_test


class DummyMessage:
    def __init__(self, chat_id: int = 123) -> None:
        self.chat = SimpleNamespace(id=chat_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)
        return SimpleNamespace(message_id=900 + len(self.answers), date=SimpleNamespace())


class DummySessionMemoryService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.recorded_messages: list[dict[str, object]] = []

    async def record_message(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.recorded_messages.append(kwargs)

    async def record_bot_reply(
        self,
        *,
        chat_id: int,
        telegram_message_id: int,
        message_text: str,
        message_ts_utc,
        bot_username: str | None,
    ) -> None:
        self.calls.append(
            {
                "chat_id": chat_id,
                "telegram_message_id": telegram_message_id,
                "message_text": message_text,
                "message_ts_utc": message_ts_utc,
                "bot_username": bot_username,
                "user_id": BOT_SESSION_USER_ID,
            }
        )


class DummyActivityService:
    async def record_message(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None


class DummyAiService:
    async def generate_morning_greeting(self, *, summary_date, summaries):  # type: ignore[no-untyped-def]
        return "Доброе утро!"


class DummyBot:
    pass


def _make_config(monkeypatch: pytest.MonkeyPatch) -> AppConfig:
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return AppConfig(_env_file=None)  # type: ignore[call-arg]


def test_is_ai_trigger_matches_bot_username():
    message = cast(
        Message,
        SimpleNamespace(
            text="Привет, @family_bot",
            caption=None,
            reply_to_message=None,
        ),
    )

    assert _is_ai_trigger(message, bot_username="family_bot", bot_user_id=None) is True


def test_is_ai_trigger_matches_reply_to_bot():
    message = cast(
        Message,
        SimpleNamespace(
            text="Ответ",
            caption=None,
            reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=42)),
        ),
    )

    assert _is_ai_trigger(message, bot_username=None, bot_user_id=42) is True


def test_build_ai_context_includes_author_and_message_text():
    message = cast(
        Message,
        SimpleNamespace(
            text="Как дела?",
            caption=None,
            reply_to_message=None,
            from_user=SimpleNamespace(full_name="Andrei", username="andrei"),
        ),
    )

    context = _build_ai_context(message)

    assert "Andrei" in context
    assert "Как дела?" in context


def test_build_ai_context_includes_bot_message_and_user_reply():
    message = cast(
        Message,
        SimpleNamespace(
            text="А завтра?",
            caption=None,
            reply_to_message=SimpleNamespace(text="Сегодня в Минске прохладно.", caption=None),
            from_user=SimpleNamespace(full_name="Andrei", username="andrei"),
        ),
    )

    context = _build_ai_context(message)

    assert "bot_message: Сегодня в Минске прохладно." in context
    assert "user_reply: А завтра?" in context


def test_bot_reply_can_be_captured_with_default_bot_user_id():
    session_memory_service = DummySessionMemoryService()

    import asyncio

    asyncio.run(
        session_memory_service.record_bot_reply(
            chat_id=123,
            telegram_message_id=55,
            message_text="Привет!",
            message_ts_utc=SimpleNamespace(),
            bot_username="family_bot",
        )
    )

    assert session_memory_service.calls == [
        {
            "chat_id": 123,
            "telegram_message_id": 55,
            "message_text": "Привет!",
            "message_ts_utc": session_memory_service.calls[0]["message_ts_utc"],
            "bot_username": "family_bot",
            "user_id": 0,
        }
    ]


def test_is_active_bot_status_matches_member_like_statuses():
    assert _is_active_bot_status("member") is True
    assert _is_active_bot_status("administrator") is True
    assert _is_active_bot_status("left") is False
    assert _is_active_bot_status("kicked") is False


def test_test_command_action_matches_supported_commands():
    assert _test_command_action("/test_morning") == "good_morning"
    assert _test_command_action("/test_night@family_bot") == "good_night_and_activity"
    assert _test_command_action("/weather_test") == "weather_test"
    assert _test_command_action("/start") is None


def test_test_command_action_ignores_empty_text():
    assert _test_command_action("") is None
    assert _test_command_action("   ") is None


@pytest.mark.asyncio
async def test_handle_test_command_returns_weather_summary(monkeypatch: pytest.MonkeyPatch):
    message = DummyMessage()
    weather_service = DummyWeatherService("В Минске прохладно.")
    session_memory_service = DummySessionMemoryService()

    handled = await _handle_test_command(
        action="weather_test",
        message=message,  # type: ignore[arg-type]
        bot=DummyBot(),
        config=_make_config(monkeypatch),
        activity_service=DummyActivityService(),  # type: ignore[arg-type]
        ai_service=DummyAiService(),  # type: ignore[arg-type]
        weather_service=weather_service,  # type: ignore[arg-type]
        chat_registry=DummyChatRegistry(allow_test=True),  # type: ignore[arg-type]
        session_memory_service=session_memory_service,  # type: ignore[arg-type]
        bot_username="family_bot",
        logger=logging.getLogger("test"),
    )

    assert handled is True
    assert weather_service.calls == 1
    assert message.answers == ["В Минске прохладно."]
    assert session_memory_service.recorded_messages == []
    assert session_memory_service.calls[0]["message_text"] == "В Минске прохладно."
    assert session_memory_service.calls[0]["bot_username"] == "family_bot"


@pytest.mark.asyncio
async def test_handle_test_command_rejects_when_test_commands_disabled(monkeypatch: pytest.MonkeyPatch):
    message = DummyMessage()
    weather_service = DummyWeatherService()

    handled = await _handle_test_command(
        action="weather_test",
        message=message,  # type: ignore[arg-type]
        bot=DummyBot(),
        config=_make_config(monkeypatch),
        activity_service=DummyActivityService(),  # type: ignore[arg-type]
        ai_service=DummyAiService(),  # type: ignore[arg-type]
        weather_service=weather_service,  # type: ignore[arg-type]
        chat_registry=DummyChatRegistry(allow_test=False),  # type: ignore[arg-type]
        session_memory_service=None,
        bot_username="family_bot",
        logger=logging.getLogger("test"),
    )

    assert handled is True
    assert weather_service.calls == 0
    assert message.answers == ["Тестовые команды для этого чата отключены."]
