from __future__ import annotations

import httpx

from app.core.models import WeatherObservation


_WEATHER_CODE_DESCRIPTIONS = {
    0: "ясно",
    1: "в основном ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь и туман",
    51: "слабая морось",
    53: "морось",
    55: "сильная морось",
    56: "слабая ледяная морось",
    57: "ледяная морось",
    61: "слабый дождь",
    63: "дождь",
    65: "сильный дождь",
    66: "слабый ледяной дождь",
    67: "ледяной дождь",
    71: "слабый снег",
    73: "снег",
    75: "сильный снег",
    77: "снежные зерна",
    80: "кратковременный слабый дождь",
    81: "кратковременный дождь",
    82: "сильный ливень",
    85: "слабый снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с небольшим градом",
    99: "гроза с градом",
}


class OpenMeteoWeatherClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=20.0)
        self._owns_client = client is None

    async def fetch_current_weather(self, city_name: str) -> WeatherObservation:
        geocode_response = await self._client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city_name, "count": 1, "language": "ru", "format": "json"},
        )
        geocode_response.raise_for_status()
        geocode_data = geocode_response.json()
        results = geocode_data.get("results") or []
        if not results:
            raise ValueError(f"City not found: {city_name}")

        location = results[0]
        latitude = float(location["latitude"])
        longitude = float(location["longitude"])

        weather_response = await self._client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                "timezone": "auto",
                "forecast_days": 1,
            },
        )
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        current = weather_data.get("current")
        if not isinstance(current, dict):
            raise ValueError(f"Current weather is missing for city: {city_name}")

        condition_code = int(current["weather_code"])
        return WeatherObservation(
            city=city_name,
            latitude=latitude,
            longitude=longitude,
            temperature_c=float(current["temperature_2m"]),
            apparent_temperature_c=float(current["apparent_temperature"]),
            condition_code=condition_code,
            condition_text=_WEATHER_CODE_DESCRIPTIONS.get(condition_code, "неизвестная погода"),
            wind_speed_m_s=float(current["wind_speed_10m"]),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
