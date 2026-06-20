from __future__ import annotations

from typing import Protocol


BASE_FAMILY_PROMPT = (
    "You are a Telegram bot assistant for the Zubrytski family chat.\n"
    "Family members: Sasha, Inna, Andrei, Alyona.\n\n"
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

    async def reply_to_mention(self, context: str) -> str:
        prompt = (
            f"{BASE_FAMILY_PROMPT}\n\n"
            "Тебя упомянули в семейном чате или тебе ответили. Ответь естественно и по‑русски.\n"
            "Если в контексте есть `bot_message` и `user_reply`, учитывай оба сообщения как продолжение диалога.\n\n"
            f"Сообщение из чата:\n{context}\n\n"
            "Сформулируй короткий, дружелюбный ответ от имени семейного бота."
        )
        return await self._call_with_fallback(prompt)

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
        prompt = (
            f"{BASE_FAMILY_PROMPT}\n\n"
            "Подготовь утреннюю сводку погоды по-русски для семейного чата.\n"
            "- Суммируй прогноз на утро, день и вечер.\n"
            "- Отдельно упомяни, когда вероятен дождь.\n"
            "- Упомяни ветер, если он заметный.\n"
            "- Упомяни UV и посоветуй SPF, если UV высокий.\n"
            "- Не выдумывай факты, которых нет в данных.\n"
            "- Сохрани стиль коротким, тёплым и практичным.\n\n"
            "Структурированные данные о погоде:\n"
            f"{weather_payload}\n\n"
            "Сформулируй компактную утреннюю сводку для чата."
        )
        return await self._call_with_fallback(prompt)
