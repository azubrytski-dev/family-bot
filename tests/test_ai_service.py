from __future__ import annotations

import pytest

from app.core.services.ai_service import AiService, BASE_FAMILY_PROMPT


class DummyClient:
    def __init__(self) -> None:
        self.last_prompt: str | None = None
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        # Echo back a short fixed answer to simulate AI behavior.
        return "Привет, зубры! Я тут и готов помочь."

    async def generate_messages(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return "Общая сводка по всем городам готова."


@pytest.mark.asyncio
async def test_reply_to_mention_uses_base_prompt():
    client = DummyClient()
    service = AiService(primary=client)

    reply = await service.reply_to_mention("Привет, бот!")

    assert "Привет" in reply
    assert client.last_prompt is not None
    assert BASE_FAMILY_PROMPT in client.last_prompt


@pytest.mark.asyncio
async def test_reply_to_mention_mentions_reply_context_format():
    client = DummyClient()
    service = AiService(primary=client)

    await service.reply_to_mention("bot_message: Привет\nuser_reply: А что дальше?")

    assert client.last_prompt is not None
    assert "bot_message" in client.last_prompt
    assert "user_reply" in client.last_prompt


@pytest.mark.asyncio
async def test_generate_weather_summary_uses_base_prompt_and_payload():
    client = DummyClient()
    service = AiService(primary=client)

    await service.generate_weather_summary('{"cities":[{"city":"Minsk"}]}')

    assert client.last_prompt is not None
    assert BASE_FAMILY_PROMPT in client.last_prompt
    assert '"city":"Minsk"' in client.last_prompt


@pytest.mark.asyncio
async def test_generate_weather_morning_summary_uses_system_prompt_and_template():
    client = DummyClient()
    service = AiService(primary=client)

    summary = await service.generate_weather_morning_summary('{"cities":[{"city":"Minsk"},{"city":"Tbilisi"}]}')

    assert summary == "Общая сводка по всем городам готова."
    assert client.last_system_prompt is not None
    assert BASE_FAMILY_PROMPT in client.last_system_prompt
    assert "ОДНО общее сообщение" in client.last_system_prompt
    assert "Начни сообщение с даты" in client.last_system_prompt
    assert "температуру" in client.last_system_prompt
    assert "ветер" in client.last_system_prompt
    assert "эмодзи" in client.last_system_prompt
    assert client.last_user_prompt is not None
    assert "Шаблон ответа" in client.last_user_prompt
    assert "Первая строка: дата" in client.last_user_prompt
    assert '"city":"Minsk"' in client.last_user_prompt
    assert '"city":"Tbilisi"' in client.last_user_prompt
