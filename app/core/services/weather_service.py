from __future__ import annotations

import asyncio
import json
import logging
from typing import Iterable, Protocol

from app.core.models import WeatherObservation
from app.core.services.ai_service import AiService


class WeatherConfigRepository(Protocol):
    async def list_enabled_values(self, parameter: str) -> Iterable[str]: ...


class WeatherClient(Protocol):
    async def fetch_current_weather(self, city_name: str) -> WeatherObservation: ...


class WeatherService:
    def __init__(
        self,
        config_repo: WeatherConfigRepository,
        weather_client: WeatherClient,
        ai_service: AiService,
    ) -> None:
        self._config_repo = config_repo
        self._weather_client = weather_client
        self._ai_service = ai_service
        self._logger = logging.getLogger(__name__)

    async def build_weather_summary(self) -> str:
        configured_cities = [city for city in await self._config_repo.list_enabled_values("weather.city") if city]
        if not configured_cities:
            return "Не настроены города для погоды. Добавьте записи weather.city в базу."

        results = await asyncio.gather(
            *(self._weather_client.fetch_current_weather(city) for city in configured_cities),
            return_exceptions=True,
        )

        observations: list[WeatherObservation] = []
        for city, result in zip(configured_cities, results, strict=True):
            if isinstance(result, Exception):
                self._logger.warning("Failed to fetch weather for %s: %s", city, result)
                continue
            observations.append(result)

        if not observations:
            return "Сейчас не получилось получить погоду. Попробуйте ещё раз чуть позже."

        weather_payload = self._build_weather_payload(observations)
        try:
            return await self._ai_service.generate_weather_summary(weather_payload)
        except Exception:
            self._logger.exception("AI weather summary generation failed; using deterministic fallback.")
            return self._build_fallback_summary(observations)

    def _build_weather_payload(self, observations: list[WeatherObservation]) -> str:
        payload = {
            "cities": [
                {
                    "city": item.city,
                    "temperature_c": round(item.temperature_c),
                    "apparent_temperature_c": round(item.apparent_temperature_c),
                    "condition": item.condition_text,
                    "wind_speed_m_s": round(item.wind_speed_m_s, 1),
                }
                for item in observations
            ]
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _build_fallback_summary(self, observations: list[WeatherObservation]) -> str:
        parts = [
            (
                f"В {item.city} {item.condition_text}, около {self._format_temp(item.temperature_c)}°C"
                f", ощущается как {self._format_temp(item.apparent_temperature_c)}°C"
            )
            for item in observations
        ]
        suggestion = self._build_clothing_hint(observations)
        return f"{'; '.join(parts)}. {suggestion}".strip()

    def _build_clothing_hint(self, observations: list[WeatherObservation]) -> str:
        coldest = min(item.apparent_temperature_c for item in observations)
        if coldest <= 0:
            return "Лучше одеться тепло: куртка, тёплая обувь и, возможно, шапка."
        if coldest <= 10:
            return "Лучше взять куртку или другую тёплую верхнюю одежду."
        if coldest <= 18:
            return "Подойдёт лёгкая верхняя одежда или кофта."
        return "Можно одеться легко по погоде."

    @staticmethod
    def _format_temp(value: float) -> str:
        rounded = round(value)
        return f"+{rounded}" if rounded > 0 else str(rounded)
