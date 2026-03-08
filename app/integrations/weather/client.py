from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class WeatherReading:
    city: str
    temperature: float | None
    feels_like: float | None
    condition: str | None
    wind_speed: float | None
    raw_payload: dict[str, Any] | None


class WeatherClientError(Exception):
    pass


class WeatherApiClient:
    """
    Minimal OpenWeatherMap-based client for current weather.

    It expects:
    - API key: provided separately (see AppConfig.WEATHER_API_KEY)
    - Base URL (optional): defaults to https://api.openweathermap.org/data/2.5
    """

    def __init__(self, api_key: str, base_url: str = "https://api.openweathermap.org/data/2.5") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=10.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_current(self, city: str) -> WeatherReading | None:
        """
        Fetch current weather for a city.

        Returns a normalized WeatherReading or None on non-fatal errors.
        """
        params = {
            "q": city,
            "appid": self._api_key,
            "units": "metric",
            "lang": "ru",
        }
        try:
            resp = await self._client.get(f"{self._base_url}/weather", params=params)
        except httpx.RequestError:
            return None

        if resp.status_code != 200:
            return None

        data = resp.json()
        main = data.get("main") or {}
        wind = data.get("wind") or {}
        weather_list = data.get("weather") or []
        condition = None
        if weather_list:
            condition = weather_list[0].get("description")

        return WeatherReading(
            city=city,
            temperature=_safe_float(main.get("temp")),
            feels_like=_safe_float(main.get("feels_like")),
            condition=condition,
            wind_speed=_safe_float(wind.get("speed")),
            raw_payload=data,
        )


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

