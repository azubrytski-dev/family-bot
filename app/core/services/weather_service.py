from __future__ import annotations

import asyncio
import json
import logging
from typing import Iterable, Protocol

from app.core.models import SevereWeatherAlert, WeatherForecast, WeatherObservation, WeatherTimeSlot
from app.core.services.ai_service import AiService


class WeatherConfigRepository(Protocol):
    async def list_enabled_values(self, parameter: str) -> Iterable[str]: ...


class WeatherClient(Protocol):
    async def fetch_current_weather(self, city_name: str) -> WeatherObservation: ...

    async def fetch_city_forecast(self, city_name: str) -> WeatherForecast: ...


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

    async def build_morning_forecast_summary(self) -> str:
        forecasts = await self._load_city_forecasts()
        if not forecasts:
            return "Сейчас не получилось собрать утреннюю сводку погоды. Попробуйте ещё раз чуть позже."

        weather_payload = self._build_morning_payload(forecasts)
        try:
            return await self._ai_service.generate_weather_morning_summary(weather_payload)
        except Exception:
            self._logger.exception("AI morning weather summary generation failed; using deterministic fallback.")
            return self._build_morning_fallback_summary(forecasts)

    async def build_severe_weather_alerts(self) -> list[str]:
        forecasts = await self._load_city_forecasts()
        messages: list[str] = []
        for forecast in forecasts:
            if not forecast.severe_alerts:
                continue
            messages.append(self._format_severe_alert_message(forecast.current.city, forecast.severe_alerts))
        return messages

    async def _load_city_forecasts(self) -> list[WeatherForecast]:
        configured_cities = [city for city in await self._config_repo.list_enabled_values("weather.city") if city]
        if not configured_cities:
            self._logger.info("No weather.city config rows found for weather forecast flow.")
            return []

        results = await asyncio.gather(
            *(self._weather_client.fetch_city_forecast(city) for city in configured_cities),
            return_exceptions=True,
        )

        forecasts: list[WeatherForecast] = []
        for city, result in zip(configured_cities, results, strict=True):
            if isinstance(result, Exception):
                self._logger.warning("Failed to fetch forecast for %s: %s", city, result)
                continue
            forecasts.append(result)
        return forecasts

    def _build_weather_payload(self, observations: list[WeatherObservation]) -> str:
        payload = {
            "cities": [
                {
                    "city": item.city,
                    "temperature_c": round(item.temperature_c),
                    "apparent_temperature_c": round(item.apparent_temperature_c),
                    "condition": item.condition_text,
                    "wind_speed_kmh": round(item.wind_speed_km_h, 1),
                }
                for item in observations
            ]
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _build_morning_payload(self, forecasts: list[WeatherForecast]) -> str:
        forecast_date = forecasts[0].morning.time_iso.split("T", maxsplit=1)[0]
        payload = {
            "date": forecast_date,
            "cities": [
                {
                    "city": forecast.current.city,
                    "утро": self._slot_payload(forecast.morning),
                    "день": self._slot_payload(forecast.afternoon),
                    "вечер": self._slot_payload(forecast.evening),
                    "daily_uv_index_max": round(forecast.daily_uv_index_max, 1),
                    "daily_precipitation_probability_max": forecast.daily_precipitation_probability_max,
                    "daily_wind_gust_max_kmh": round(forecast.daily_wind_gust_max_km_h, 1),
                    "alerts": [
                        {
                            "emoji": alert.emoji,
                            "title": alert.title,
                            "details": alert.details,
                        }
                        for alert in forecast.severe_alerts
                    ],
                }
                for forecast in forecasts
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

    def _build_morning_fallback_summary(self, forecasts: list[WeatherForecast]) -> str:
        return "\n\n".join(self._build_city_forecast_block(forecast) for forecast in forecasts)

    def _build_city_forecast_block(self, forecast: WeatherForecast) -> str:
        slots = [forecast.morning, forecast.afternoon, forecast.evening]
        rain_slots = [slot.label for slot in slots if slot.precipitation_probability >= 55]
        windy_slots = [slot.label for slot in slots if slot.wind_gust_km_h >= 25]
        uv_part = f"UV: до {round(forecast.daily_uv_index_max, 1)}."
        if forecast.daily_uv_index_max >= 6:
            uv_part += " SPF пригодится."
        rain_part = (
            f"Дождь вероятнее: {', '.join(rain_slots)}."
            if rain_slots
            else "Дождь маловероятен."
        )
        wind_part = (
            f"Ветер заметный: {', '.join(windy_slots)}."
            if windy_slots
            else "Сильного ветра не ожидается."
        )
        alert_part = ""
        if forecast.severe_alerts:
            alert_part = " ".join(
                f"{alert.emoji} {alert.title}: {alert.details}"
                for alert in forecast.severe_alerts
            )
            alert_part = f"\nПредупреждение: {alert_part}"

        return (
            f"{forecast.current.city}\n"
            f"Утро: {self._slot_brief(forecast.morning)}.\n"
            f"День: {self._slot_brief(forecast.afternoon)}.\n"
            f"Вечер: {self._slot_brief(forecast.evening)}.\n"
            f"{rain_part}\n"
            f"{wind_part}\n"
            f"{uv_part}"
            f"{alert_part}"
        ).strip()

    def _build_clothing_hint(self, observations: list[WeatherObservation]) -> str:
        coldest = min(item.apparent_temperature_c for item in observations)
        if coldest <= 0:
            return "Лучше одеться тепло: куртка, тёплая обувь и, возможно, шапка."
        if coldest <= 10:
            return "Лучше взять куртку или другую тёплую верхнюю одежду."
        if coldest <= 18:
            return "Подойдёт лёгкая верхняя одежда или кофта."
        return "Можно одеться легко по погоде."

    def _format_severe_alert_message(self, city: str, alerts: list[SevereWeatherAlert]) -> str:
        unique_parts: list[str] = []
        for alert in alerts:
            part = f"{alert.emoji} {alert.title}: {alert.details}"
            if part not in unique_parts:
                unique_parts.append(part)
        return f"Погодное предупреждение для {city}: " + " ".join(unique_parts)

    @staticmethod
    def _slot_brief(slot: WeatherTimeSlot) -> str:
        return (
            f"{slot.weather_text}, {WeatherService._format_temp(slot.temperature_c)}°C, "
            f"ветер {round(slot.wind_speed_km_h)} км/ч"
        )

    @staticmethod
    def _slot_payload(slot: WeatherTimeSlot) -> dict[str, object]:
        return {
            "time": slot.time_iso,
            "temperature_c": round(slot.temperature_c),
            "apparent_temperature_c": round(slot.apparent_temperature_c),
            "condition": slot.weather_text,
            "precipitation_probability": slot.precipitation_probability,
            "precipitation_mm": round(slot.precipitation_mm, 1),
            "wind_speed_kmh": round(slot.wind_speed_km_h, 1),
            "wind_gust_kmh": round(slot.wind_gust_km_h, 1),
            "uv_index": round(slot.uv_index, 1),
        }

    @staticmethod
    def _format_temp(value: float) -> str:
        rounded = round(value)
        return f"+{rounded}" if rounded > 0 else str(rounded)
