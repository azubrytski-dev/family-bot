from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from app.bot.handlers import (
    _build_ai_context,
    _handle_test_command,
    _is_active_bot_status,
    _is_ai_trigger,
    _test_command_action,
)
from app.core.config import AppConfig


class DummyWeatherService:
    def __init__(self, summary: str = "Погода готова.") -> None:
        self.summary = summary
        self.calls = 0

    async def build_weather_summary(self) -> str:
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


class DummyActivityService:
    async def record_message(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None


class DummyBot:
    pass


def _make_config(monkeypatch: pytest.MonkeyPatch) -> AppConfig:
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return AppConfig(_env_file=None)  # type: ignore[call-arg]


def test_is_ai_trigger_matches_bot_username():
    message = SimpleNamespace(
        text="Привет, @family_bot",
        caption=None,
        reply_to_message=None,
    )

    assert _is_ai_trigger(message, bot_username="family_bot", bot_user_id=None) is True


def test_is_ai_trigger_matches_reply_to_bot():
    message = SimpleNamespace(
        text="Ответ",
        caption=None,
        reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=42)),
    )

    assert _is_ai_trigger(message, bot_username=None, bot_user_id=42) is True


def test_build_ai_context_includes_author_and_message_text():
    message = SimpleNamespace(
        text="Как дела?",
        caption=None,
        from_user=SimpleNamespace(full_name="Andrei", username="andrei"),
    )

    context = _build_ai_context(message)

    assert "Andrei" in context
    assert "Как дела?" in context


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


@pytest.mark.asyncio
async def test_handle_test_command_returns_weather_summary(monkeypatch: pytest.MonkeyPatch):
    message = DummyMessage()
    weather_service = DummyWeatherService("В Минске прохладно.")

    handled = await _handle_test_command(
        action="weather_test",
        message=message,  # type: ignore[arg-type]
        bot=DummyBot(),
        config=_make_config(monkeypatch),
        activity_service=DummyActivityService(),  # type: ignore[arg-type]
        weather_service=weather_service,  # type: ignore[arg-type]
        chat_registry=DummyChatRegistry(allow_test=True),  # type: ignore[arg-type]
        logger=logging.getLogger("test"),
    )

    assert handled is True
    assert weather_service.calls == 1
    assert message.answers == ["В Минске прохладно."]


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
        weather_service=weather_service,  # type: ignore[arg-type]
        chat_registry=DummyChatRegistry(allow_test=False),  # type: ignore[arg-type]
        logger=logging.getLogger("test"),
    )

    assert handled is True
    assert weather_service.calls == 0
    assert message.answers == ["Тестовые команды для этого чата отключены."]
