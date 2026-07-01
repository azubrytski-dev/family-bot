from __future__ import annotations

from datetime import date, datetime

import pytest

from app.core.models import SessionMessage
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

    assert reply == "Общая сводка по всем городам готова."
    assert client.last_system_prompt is not None
    assert BASE_FAMILY_PROMPT in client.last_system_prompt
    assert client.last_user_prompt is not None
    assert "Привет, бот!" in client.last_user_prompt


@pytest.mark.asyncio
async def test_reply_to_mention_mentions_reply_context_format():
    client = DummyClient()
    service = AiService(primary=client)

    await service.reply_to_mention("bot_message: Привет\nuser_reply: А что дальше?")

    assert client.last_system_prompt is not None
    assert "не знаешь" not in client.last_system_prompt.lower()
    assert "Не начинай каждый ответ заново с приветствия" in client.last_system_prompt
    assert "Если есть признаки продолжающегося разговора" in client.last_system_prompt
    assert "Приветствие допустимо только если это действительно похоже на самое первое сообщение" in client.last_system_prompt
    assert "Последние сообщения автора" in client.last_system_prompt
    assert "главный источник недавнего личного контекста" in client.last_system_prompt
    assert "Последняя погодная сводка бота" in client.last_system_prompt
    assert "используй точные значения" in client.last_system_prompt
    assert "Не выдумывай погоду" in client.last_system_prompt
    assert "Недавние сводки сессий" in client.last_system_prompt
    assert "Недавний контекст текущей сессии" in client.last_system_prompt
    assert "reply_to_bot=yes" in client.last_system_prompt
    assert "1-2 уместных эмодзи" in client.last_system_prompt
    assert client.last_user_prompt is not None
    assert "bot_message" in client.last_user_prompt
    assert "user_reply" in client.last_user_prompt


@pytest.mark.asyncio
async def test_reply_to_mention_system_prompt_marks_pet_names_as_known_facts():
    client = DummyClient()
    service = AiService(primary=client)

    await service.reply_to_mention("Как зовут кота Алены?")

    assert client.last_system_prompt is not None
    assert "The family dog's name is Малыш." in client.last_system_prompt
    assert "Alyona's cat's name is Луник." in client.last_system_prompt
    assert "Do not say that you do not know these names." in client.last_system_prompt


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


@pytest.mark.asyncio
async def test_generate_session_summary_uses_safe_russian_prompt():
    client = DummyClient()
    service = AiService(primary=client)

    await service.generate_session_summary(
        started_at_utc=datetime.fromisoformat("2026-06-23T08:00:00+00:00"),
        completed_at_utc=datetime.fromisoformat("2026-06-23T14:00:00+00:00"),
        messages=[
            SessionMessage(
                id=1,
                session_id=1,
                chat_id=1,
                telegram_message_id=10,
                user_id=101,
                username="andrei",
                display_name="Andrei",
                message_text="У Алены завтра экзамен.",
                message_ts_utc=datetime.fromisoformat("2026-06-23T09:00:00+00:00"),
                local_date=date.fromisoformat("2026-06-23"),
                is_reply_to_bot=False,
            )
        ],
    )

    assert client.last_prompt is not None
    assert BASE_FAMILY_PROMPT in client.last_prompt
    assert "Максимум 500 символов" in client.last_prompt
    assert "компактную историю разговора" in client.last_prompt
    assert "Обязательно укажи имена участников" in client.last_prompt
    assert "Сохраняй хронологию" in client.last_prompt
    assert "не драматизируй" in client.last_prompt
    assert "Andrei" in client.last_prompt
    assert "У Алены завтра экзамен." in client.last_prompt


@pytest.mark.asyncio
async def test_generate_session_summary_prompt_includes_multi_speaker_history_context():
    client = DummyClient()
    service = AiService(primary=client)

    await service.generate_session_summary(
        started_at_utc=datetime.fromisoformat("2026-06-23T08:00:00+00:00"),
        completed_at_utc=datetime.fromisoformat("2026-06-23T14:00:00+00:00"),
        messages=[
            SessionMessage(
                id=1,
                session_id=1,
                chat_id=1,
                telegram_message_id=10,
                user_id=101,
                username="andrei",
                display_name="Andrei",
                message_text="Предлагаю вечером погулять с Малышом.",
                message_ts_utc=datetime.fromisoformat("2026-06-23T09:00:00+00:00"),
                local_date=date.fromisoformat("2026-06-23"),
                is_reply_to_bot=False,
            ),
            SessionMessage(
                id=2,
                session_id=1,
                chat_id=1,
                telegram_message_id=11,
                user_id=102,
                username="inna",
                display_name="Inna",
                message_text="Я могу купить что-то к ужину.",
                message_ts_utc=datetime.fromisoformat("2026-06-23T09:30:00+00:00"),
                local_date=date.fromisoformat("2026-06-23"),
                is_reply_to_bot=False,
            ),
            SessionMessage(
                id=3,
                session_id=1,
                chat_id=1,
                telegram_message_id=12,
                user_id=103,
                username="alyona",
                display_name="Alyona",
                message_text="У меня сначала экзамен, потом смогу написать.",
                message_ts_utc=datetime.fromisoformat("2026-06-23T10:00:00+00:00"),
                local_date=date.fromisoformat("2026-06-23"),
                is_reply_to_bot=False,
            ),
        ],
    )

    assert client.last_prompt is not None
    assert "Andrei" in client.last_prompt
    assert "Inna" in client.last_prompt
    assert "Alyona" in client.last_prompt
    assert "Предлагаю вечером погулять с Малышом." in client.last_prompt
    assert "Я могу купить что-то к ужину." in client.last_prompt
    assert "У меня сначала экзамен, потом смогу написать." in client.last_prompt


@pytest.mark.asyncio
async def test_generate_morning_greeting_uses_summary_context():
    client = DummyClient()
    service = AiService(primary=client)

    summary = await service.generate_morning_greeting(
        summary_date=date.fromisoformat("2026-06-23"),
        summaries=["Вчера обсуждали экзамен Алены и прогулку с Малышом."],
    )

    assert summary == "Общая сводка по всем городам готова."
    assert client.last_system_prompt is not None
    assert "доброе утреннее сообщение" in client.last_system_prompt
    assert "1-3 уместных эмодзи" in client.last_system_prompt
    assert "не драматизируй" in client.last_system_prompt
    assert client.last_user_prompt is not None
    assert "2026-06-23" in client.last_user_prompt
    assert "прогулку с Малышом" in client.last_user_prompt


@pytest.mark.asyncio
async def test_generate_evening_greeting_uses_yesterday_and_today_summaries():
    client = DummyClient()
    service = AiService(primary=client)

    summary = await service.generate_evening_greeting(
        yesterday_date=date.fromisoformat("2026-06-23"),
        today_date=date.fromisoformat("2026-06-24"),
        yesterday_summaries=["Вчера говорили про планы на утро."],
        today_summaries=["Сегодня успели сходить по делам и вспомнить про Малыша."],
    )

    assert summary == "Общая сводка по всем городам готова."
    assert client.last_system_prompt is not None
    assert "вечернее сообщение" in client.last_system_prompt
    assert "1-3 уместных эмодзи" in client.last_system_prompt
    assert client.last_user_prompt is not None
    assert "2026-06-23" in client.last_user_prompt
    assert "2026-06-24" in client.last_user_prompt
    assert "вспомнить про Малыша" in client.last_user_prompt
