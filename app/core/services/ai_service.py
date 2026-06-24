from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, Sequence

from app.core.models import SessionMessage


BASE_FAMILY_PROMPT = (
    "You are a Telegram bot assistant for the Zubrytski family chat.\n"
    "Family members: Sasha, Inna, Andrei, Alyona.\n\n"
    "Known family facts:\n"
    "- The family dog's name is Малыш.\n"
    "- Alyona's cat's name is Луник.\n"
    "- Treat these names as known facts.\n"
    "- Do not say that you do not know these names.\n\n"
    "Your style:\n"
    "- friendly\n"
    "- positive\n"
    "- warm\n"
    "- concise\n"
    "- usually 20 to 80 words\n"
    "- answer naturally in Russian\n"
    "- avoid being too formal\n"
    "- be practical and helpful\n"
    "- if the message is casual, answer casually\n"
    "- if the message is a question, answer directly\n"
    "- if there is not enough context, say so briefly\n"
)


class AiClient(Protocol):
    async def generate_text(self, prompt: str) -> str: ...

    async def generate_messages(self, system_prompt: str, user_prompt: str) -> str: ...


class AiService:
    def __init__(self, primary: AiClient, fallback: AiClient | None = None) -> None:
        self._primary = primary
        self._fallback = fallback

    async def _call_with_fallback(self, prompt: str) -> str:
        try:
            return await self._primary.generate_text(prompt)
        except Exception:
            if self._fallback is None:
                raise
            return await self._fallback.generate_text(prompt)

    async def _call_messages_with_fallback(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return await self._primary.generate_messages(system_prompt, user_prompt)
        except Exception:
            if self._fallback is None:
                raise
            return await self._fallback.generate_messages(system_prompt, user_prompt)

    async def reply_to_mention(self, context: str) -> str:
        system_prompt = (
            f"{BASE_FAMILY_PROMPT}\n\n"
            "Тебя упомянули в семейном чате или тебе ответили. Ответь естественно и по‑русски.\n"
            "Если в контексте есть `bot_message` и `user_reply`, учитывай оба сообщения как продолжение диалога.\n\n"
            "Если вопрос касается известных фактов о семье или питомцах, отвечай на основе этих фактов уверенно и без оговорок.\n"
        )
        user_prompt = (
            f"Сообщение из чата:\n{context}\n\n"
            "Сформулируй короткий, дружелюбный ответ от имени семейного бота."
        )
        return await self._call_messages_with_fallback(system_prompt, user_prompt)

    async def generate_weather_summary(self, weather_payload: str) -> str:
        prompt = (
            f"{BASE_FAMILY_PROMPT}\n\n"
            "Опиши погоду по-русски коротко и практично.\n"
            "Укажи дату в начале предложения.\n"
            "- Упомяни все города из данных.\n"
            "- Не выдумывай факты, которых нет в данных.\n"
            "- Не перегружай ответ деталями.\n"
            "- Добавь короткую подсказку, что лучше надеть.\n"
            "- Избегай медицинских и опасных рекомендаций.\n"
            "- Сделай итог компактным.\n\n"
            "Структурированные данные о погоде:\n"
            f"{weather_payload}\n\n"
            "Сформулируй 1-2 коротких предложения для семейного чата."
        )
        return await self._call_with_fallback(prompt)

    async def generate_weather_morning_summary(self, weather_payload: str) -> str:
        system_prompt = (
            f"{BASE_FAMILY_PROMPT}\n\n"
            "Ты готовишь ОДНО общее сообщение о погоде для семейного Telegram-чата сразу по всем городам из данных.\n"
            "Ответ должен быть на русском языке, средней длины, достаточно подробным, но не перегруженным.\n"
            "Пиши одним сообщением для всех городов, не разбивай на отдельные ответы.\n"
            "Начни сообщение с даты из входных данных.\n"
            "Для каждого города обязательно укажи утро, день и вечер.\n"
            "Для каждого города обязательно укажи температуру для утра, дня и вечера в °C.\n"
            "Для каждого города обязательно укажи ветер для утра, дня и вечера в км/ч.\n"
            "Обязательно укажи, когда вероятен дождь.\n"
            "Обязательно укажи UV index числом, если он высокий.\n"
            "Если UV высокий, прямо посоветуй использовать SPF.\n"
            "Если есть опасные погодные условия, обязательно добавь короткое предупреждение с эмодзи.\n"
            "Добавь немного уместных погодных эмодзи, но без перегруза.\n"
            "Не выдумывай факты, которых нет в данных.\n"
            "Сделай итог тёплым, практичным и удобным для чтения в Telegram.\n"
            "Длина ответа: средняя, примерно 7-12 коротких строк или один аккуратный средний блок текста.\n"
            "Если в ответе нет даты, температуры и ветра по каждому городу, ответ считается неполным."
        )
        user_prompt = (
            "Шаблон ответа:\n"
            "1. Первая строка: дата.\n"
            "2. Вторая строка: короткая общая фраза про день.\n"
            "3. Затем все города в одном сообщении.\n"
            "4. Для каждого города обязательно:\n"
            "   - утро: температура и ветер\n"
            "   - день: температура и ветер\n"
            "   - вечер: температура и ветер\n"
            "   - дождь: когда вероятнее\n"
            "   - UV: значение и SPF при высоком UV\n"
            "5. В конце добавь предупреждение, если есть опасные условия.\n\n"
            "Инструкции:\n"
            "- Упомяни все города из данных.\n"
            "- Сохраняй компактность, но не теряй важные детали.\n"
            "- Не используй сырые JSON-ключи в ответе.\n"
            "- Не опускай температуру.\n"
            "- Не опускай ветер.\n"
            "- Не опускай дату.\n"
            "- Не опускай UV, если он высокий.\n"
            "- Не опускай предупреждение, если есть гроза, сильный дождь или опасный ветер.\n\n"
            "Данные по погоде:\n"
            f"{weather_payload}"
        )
        return await self._call_messages_with_fallback(system_prompt, user_prompt)

    async def generate_session_summary(
        self,
        *,
        started_at_utc: datetime,
        completed_at_utc: datetime,
        messages: Sequence[SessionMessage],
    ) -> str:
        transcript = "\n".join(
            (
                f"- {message.message_ts_utc.isoformat()} | "
                f"{message.display_name or message.username or f'id:{message.user_id}'} | "
                f"reply_to_bot={'yes' if message.is_reply_to_bot else 'no'} | "
                f"{message.message_text}"
            )
            for message in messages
        )
        prompt = (
            f"{BASE_FAMILY_PROMPT}\n\n"
            "Сделай короткую семейную сводку по завершённой сессии чата.\n"
            "Обязательно пиши по-русски.\n"
            "Максимум 500 символов.\n"
            "Укажи, кто был активен, какие были ключевые темы или планы, и общий тон, только если он очевиден.\n"
            "Не пересказывай чат дословно, не цитируй слишком много и не добавляй чувствительных деталей.\n"
            "Если в сообщениях есть что-то тяжёлое или негативное, не драматизируй и не повторяй болезненные детали.\n"
            "Используй тёплый, нейтральный и практичный тон.\n\n"
            f"Сессия началась: {started_at_utc.isoformat()}\n"
            f"Сессия завершена: {completed_at_utc.isoformat()}\n"
            f"Сообщения:\n{transcript}\n\n"
            "Сформулируй одну компактную сводку для памяти бота."
        )
        return await self._call_with_fallback(prompt)

    async def generate_morning_greeting(
        self,
        *,
        summary_date: date,
        summaries: Sequence[str],
    ) -> str:
        summary_lines = "\n".join(f"- {summary}" for summary in summaries)
        system_prompt = (
            f"{BASE_FAMILY_PROMPT}\n\n"
            "Ты готовишь короткое доброе утреннее сообщение для семейного Telegram-чата.\n"
            "Обязательно пиши по-русски.\n"
            "Опирайся только на переданные сводки за вчера.\n"
            "Тон должен быть тёплым, поддерживающим, коротким и естественным.\n"
            "Добавь 1-3 уместных эмодзи, если они делают сообщение теплее и живее.\n"
            "Не перегружай сообщение эмодзи.\n"
            "Если во вчерашних сводках есть планы, дела или важные события, можно мягко их упомянуть.\n"
            "Если есть неприятные или тяжёлые события, не повторяй болезненные детали и не драматизируй.\n"
            "Лучше использовать мягкие формулировки вроде пожелания спокойного и хорошего дня.\n"
            "Ответ должен быть компактным, примерно 1-3 коротких предложения.\n"
        )
        user_prompt = (
            f"Дата сводок: {summary_date.isoformat()}\n"
            f"Сводки за вчера:\n{summary_lines}\n\n"
            "Сформулируй одно короткое утреннее сообщение для семьи."
        )
        return await self._call_messages_with_fallback(system_prompt, user_prompt)

    async def generate_evening_greeting(
        self,
        *,
        yesterday_date: date,
        today_date: date,
        yesterday_summaries: Sequence[str],
        today_summaries: Sequence[str],
    ) -> str:
        yesterday_lines = "\n".join(f"- {summary}" for summary in yesterday_summaries) or "- нет сводок"
        today_lines = "\n".join(f"- {summary}" for summary in today_summaries) or "- нет сводок"
        system_prompt = (
            f"{BASE_FAMILY_PROMPT}\n\n"
            "Ты готовишь короткое вечернее сообщение для семейного Telegram-чата.\n"
            "Обязательно пиши по-русски.\n"
            "Опирайся на сводки за вчера и за сегодня.\n"
            "Тон должен быть тёплым, спокойным, семейным и естественным.\n"
            "Добавь 1-3 уместных эмодзи, если они делают сообщение теплее и живее.\n"
            "Не перегружай сообщение эмодзи.\n"
            "Можно коротко упомянуть, как прошёл день, и пожелать спокойной ночи или хорошего вечера.\n"
            "Если есть неприятные или тяжёлые события, не повторяй болезненные детали и не драматизируй.\n"
            "Ответ должен быть компактным, примерно 1-3 коротких предложения.\n"
        )
        user_prompt = (
            f"Дата вчерашних сводок: {yesterday_date.isoformat()}\n"
            f"Вчерашние сводки:\n{yesterday_lines}\n\n"
            f"Дата сегодняшних сводок: {today_date.isoformat()}\n"
            f"Сегодняшние сводки:\n{today_lines}\n\n"
            "Сформулируй одно короткое вечернее сообщение для семьи."
        )
        return await self._call_messages_with_fallback(system_prompt, user_prompt)
