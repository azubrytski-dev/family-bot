from __future__ import annotations

import httpx

from app.core.models import SevereWeatherAlert, WeatherForecast, WeatherObservation, WeatherTimeSlot


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
        forecast = await self.fetch_city_forecast(city_name)
        return forecast.current

    async def fetch_city_forecast(self, city_name: str) -> WeatherForecast:
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
                "hourly": (
                    "temperature_2m,apparent_temperature,precipitation_probability,precipitation,"
                    "weather_code,wind_speed_10m,wind_gusts_10m,uv_index"
                ),
                "daily": "uv_index_max,precipitation_probability_max,wind_gusts_10m_max",
                "timezone": "auto",
                "forecast_days": 1,
            },
        )
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        current = weather_data.get("current")
        hourly = weather_data.get("hourly")
        daily = weather_data.get("daily")
        if not isinstance(current, dict):
            raise ValueError(f"Current weather is missing for city: {city_name}")
        if not isinstance(hourly, dict):
            raise ValueError(f"Hourly weather is missing for city: {city_name}")
        if not isinstance(daily, dict):
            raise ValueError(f"Daily weather is missing for city: {city_name}")

        condition_code = int(current["weather_code"])
        current_observation = WeatherObservation(
            city=city_name,
            latitude=latitude,
            longitude=longitude,
            temperature_c=float(current["temperature_2m"]),
            apparent_temperature_c=float(current["apparent_temperature"]),
            condition_code=condition_code,
            condition_text=_WEATHER_CODE_DESCRIPTIONS.get(condition_code, "неизвестная погода"),
            wind_speed_km_h=float(current["wind_speed_10m"]),
        )

        morning = self._build_time_slot(hourly, 9, "утро")
        afternoon = self._build_time_slot(hourly, 14, "день")
        evening = self._build_time_slot(hourly, 19, "вечер")
        daily_uv_index_max = float(self._first_daily_value(daily, "uv_index_max"))
        daily_precip_probability_max = int(round(float(self._first_daily_value(daily, "precipitation_probability_max"))))
        daily_wind_gust_max = float(self._first_daily_value(daily, "wind_gusts_10m_max"))

        return WeatherForecast(
            current=current_observation,
            morning=morning,
            afternoon=afternoon,
            evening=evening,
            daily_uv_index_max=daily_uv_index_max,
            daily_precipitation_probability_max=daily_precip_probability_max,
            daily_wind_gust_max_km_h=daily_wind_gust_max,
            severe_alerts=self._build_severe_alerts(
                city_name=city_name,
                slots=[morning, afternoon, evening],
                daily_uv_index_max=daily_uv_index_max,
                daily_wind_gust_max_km_h=daily_wind_gust_max,
            ),
        )

    def _build_time_slot(self, hourly: dict, preferred_hour: int, label: str) -> WeatherTimeSlot:
        times = hourly.get("time")
        if not isinstance(times, list) or not times:
            raise ValueError("Hourly times are missing")

        selected_index = len(times) - 1
        for index, raw_time in enumerate(times):
            time_str = str(raw_time)
            hour_value = int(time_str.split("T", maxsplit=1)[1].split(":", maxsplit=1)[0])
            if hour_value >= preferred_hour:
                selected_index = index
                break

        weather_code = int(self._hourly_value(hourly, "weather_code", selected_index))
        return WeatherTimeSlot(
            label=label,
            time_iso=str(times[selected_index]),
            temperature_c=float(self._hourly_value(hourly, "temperature_2m", selected_index)),
            apparent_temperature_c=float(self._hourly_value(hourly, "apparent_temperature", selected_index)),
            precipitation_probability=int(round(float(self._hourly_value(hourly, "precipitation_probability", selected_index)))),
            precipitation_mm=float(self._hourly_value(hourly, "precipitation", selected_index)),
            weather_code=weather_code,
            weather_text=_WEATHER_CODE_DESCRIPTIONS.get(weather_code, "неизвестная погода"),
            wind_speed_km_h=float(self._hourly_value(hourly, "wind_speed_10m", selected_index)),
            wind_gust_km_h=float(self._hourly_value(hourly, "wind_gusts_10m", selected_index)),
            uv_index=float(self._hourly_value(hourly, "uv_index", selected_index)),
        )

    def _build_severe_alerts(
        self,
        *,
        city_name: str,
        slots: list[WeatherTimeSlot],
        daily_uv_index_max: float,
        daily_wind_gust_max_km_h: float,
    ) -> list[SevereWeatherAlert]:
        alerts: list[SevereWeatherAlert] = []
        for slot in slots:
            if slot.weather_code in {95, 96, 99}:
                alerts.append(
                    SevereWeatherAlert(
                        city=city_name,
                        emoji="⛈️",
                        title="Гроза",
                        details=f"{slot.label.capitalize()}: возможна гроза, лучше быть осторожнее на улице.",
                    )
                )
                break
            if slot.precipitation_probability >= 85 and slot.precipitation_mm >= 8:
                alerts.append(
                    SevereWeatherAlert(
                        city=city_name,
                        emoji="🌧️",
                        title="Сильный дождь",
                        details=f"{slot.label.capitalize()}: вероятен сильный дождь, лучше взять зонт и непромокаемую одежду.",
                    )
                )
                break

        if daily_wind_gust_max_km_h >= 60:
            alerts.append(
                SevereWeatherAlert(
                    city=city_name,
                    emoji="💨",
                    title="Сильный ветер",
                    details="Ожидаются сильные порывы ветра, лучше быть аккуратнее на улице.",
                )
            )

        if daily_uv_index_max >= 7:
            alerts.append(
                SevereWeatherAlert(
                    city=city_name,
                    emoji="☀️",
                    title="Высокий UV",
                    details="UV сегодня высокий, если будете долго на солнце, лучше использовать SPF.",
                )
            )

        return alerts

    @staticmethod
    def _hourly_value(hourly: dict, key: str, index: int) -> float | int:
        values = hourly.get(key)
        if not isinstance(values, list) or len(values) <= index:
            raise ValueError(f"Hourly field {key} is missing")
        return values[index]

    @staticmethod
    def _first_daily_value(daily: dict, key: str) -> float | int:
        values = daily.get(key)
        if not isinstance(values, list) or not values:
            raise ValueError(f"Daily field {key} is missing")
        return values[0]

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
