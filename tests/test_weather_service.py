from __future__ import annotations

import pytest

from app.core.models import SevereWeatherAlert, WeatherForecast, WeatherObservation, WeatherTimeSlot
from app.core.services.ai_service import AiService
from app.core.services.weather_service import WeatherService


class InMemoryConfigRepo:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    async def list_enabled_values(self, parameter: str) -> list[str]:
        assert parameter == "weather.city"
        return list(self._values)


class StubWeatherClient:
    def __init__(
        self,
        responses: dict[str, WeatherObservation | Exception] | None = None,
        forecasts: dict[str, WeatherForecast | Exception] | None = None,
    ) -> None:
        self._responses = responses
        self._forecasts = forecasts or {}

    async def fetch_current_weather(self, city_name: str) -> WeatherObservation:
        if self._responses is None:
            forecast = await self.fetch_city_forecast(city_name)
            return forecast.current
        result = self._responses[city_name]
        if isinstance(result, Exception):
            raise result
        return result

    async def fetch_city_forecast(self, city_name: str) -> WeatherForecast:
        result = self._forecasts[city_name]
        if isinstance(result, Exception):
            raise result
        return result


class RecordingAiClient:
    def __init__(self, reply: str = "Погодка отличная.") -> None:
        self.reply = reply
        self.last_prompt: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.reply


class FailingAiClient:
    async def generate_text(self, prompt: str) -> str:
        raise RuntimeError("AI unavailable")


def _observation(city: str, temp: float, apparent: float, condition: str) -> WeatherObservation:
    return WeatherObservation(
        city=city,
        latitude=0.0,
        longitude=0.0,
        temperature_c=temp,
        apparent_temperature_c=apparent,
        condition_code=0,
        condition_text=condition,
        wind_speed_m_s=3.0,
    )


def _slot(
    label: str,
    temp: float,
    rain_prob: int,
    rain_mm: float,
    wind_gust: float,
    uv_index: float,
    condition: str = "ясно",
    weather_code: int = 0,
) -> WeatherTimeSlot:
    hour = 9 if label == "утро" else 14 if label == "день" else 19
    return WeatherTimeSlot(
        label=label,
        time_iso=f"2026-06-20T{hour:02d}:00",
        temperature_c=temp,
        apparent_temperature_c=temp,
        precipitation_probability=rain_prob,
        precipitation_mm=rain_mm,
        weather_code=weather_code,
        weather_text=condition,
        wind_speed_m_s=6.0,
        wind_gust_m_s=wind_gust,
        uv_index=uv_index,
    )


def _forecast(
    city: str,
    *,
    morning: WeatherTimeSlot | None = None,
    afternoon: WeatherTimeSlot | None = None,
    evening: WeatherTimeSlot | None = None,
    uv_max: float = 5.0,
    wind_gust_max: float = 9.0,
    alerts: list[SevereWeatherAlert] | None = None,
) -> WeatherForecast:
    morning_slot = morning or _slot("утро", 10, 20, 0.0, 8.0, 2.0)
    afternoon_slot = afternoon or _slot("день", 16, 30, 0.0, 10.0, 4.0)
    evening_slot = evening or _slot("вечер", 13, 25, 0.0, 9.0, 1.0)
    return WeatherForecast(
        current=_observation(city, 12, 12, "ясно"),
        morning=morning_slot,
        afternoon=afternoon_slot,
        evening=evening_slot,
        daily_uv_index_max=uv_max,
        daily_precipitation_probability_max=max(
            morning_slot.precipitation_probability,
            afternoon_slot.precipitation_probability,
            evening_slot.precipitation_probability,
        ),
        daily_wind_gust_max_m_s=wind_gust_max,
        severe_alerts=list(alerts or []),
    )


@pytest.mark.asyncio
async def test_weather_service_returns_ai_summary_for_two_cities():
    ai_client = RecordingAiClient(reply="В Минске прохладно, а в Тбилиси теплее.")
    service = WeatherService(
        config_repo=InMemoryConfigRepo(["Minsk", "Tbilisi"]),
        weather_client=StubWeatherClient(
            responses={
                "Minsk": _observation("Minsk", 6, 4, "облачно"),
                "Tbilisi": _observation("Tbilisi", 14, 14, "ясно"),
            }
        ),
        ai_service=AiService(primary=ai_client),
    )

    summary = await service.build_weather_summary()

    assert summary == "В Минске прохладно, а в Тбилиси теплее."
    assert ai_client.last_prompt is not None
    assert "Minsk" in ai_client.last_prompt
    assert "Tbilisi" in ai_client.last_prompt


@pytest.mark.asyncio
async def test_weather_service_uses_partial_success_when_one_city_fails():
    ai_client = RecordingAiClient(reply="В Минске облачно, лучше взять куртку.")
    service = WeatherService(
        config_repo=InMemoryConfigRepo(["Minsk", "Tbilisi"]),
        weather_client=StubWeatherClient(
            responses={
                "Minsk": _observation("Minsk", 7, 5, "облачно"),
                "Tbilisi": ValueError("missing city"),
            }
        ),
        ai_service=AiService(primary=ai_client),
    )

    summary = await service.build_weather_summary()

    assert summary == "В Минске облачно, лучше взять куртку."
    assert ai_client.last_prompt is not None
    assert "Minsk" in ai_client.last_prompt
    assert "Tbilisi" not in ai_client.last_prompt


@pytest.mark.asyncio
async def test_weather_service_falls_back_when_ai_fails():
    service = WeatherService(
        config_repo=InMemoryConfigRepo(["Minsk"]),
        weather_client=StubWeatherClient(responses={"Minsk": _observation("Minsk", 3, 1, "пасмурно")}),
        ai_service=AiService(primary=FailingAiClient()),
    )

    summary = await service.build_weather_summary()

    assert "Minsk" in summary
    assert "пасмурно" in summary
    assert "курт" in summary.lower()


@pytest.mark.asyncio
async def test_weather_service_fallback_stays_compact_for_two_cities():
    service = WeatherService(
        config_repo=InMemoryConfigRepo(["Minsk", "Tbilisi"]),
        weather_client=StubWeatherClient(
            responses={
                "Minsk": _observation("Minsk", 6, 4, "облачно"),
                "Tbilisi": _observation("Tbilisi", 14, 14, "ясно"),
            }
        ),
        ai_service=AiService(primary=FailingAiClient()),
    )

    summary = await service.build_weather_summary()

    assert summary.count(".") <= 2
    assert "Minsk" in summary
    assert "Tbilisi" in summary


@pytest.mark.asyncio
async def test_weather_service_reports_missing_config():
    service = WeatherService(
        config_repo=InMemoryConfigRepo([]),
        weather_client=StubWeatherClient(responses={}),
        ai_service=AiService(primary=RecordingAiClient()),
    )

    summary = await service.build_weather_summary()

    assert "weather.city" in summary


@pytest.mark.asyncio
async def test_weather_service_returns_morning_summary_from_ai():
    ai_client = RecordingAiClient(reply="Утром ясно, днём возможен дождь, SPF пригодится.")
    service = WeatherService(
        config_repo=InMemoryConfigRepo(["Minsk"]),
        weather_client=StubWeatherClient(
            forecasts={
                "Minsk": _forecast(
                    "Minsk",
                    afternoon=_slot("день", 18, 75, 4.0, 13.0, 6.5, "облачно"),
                    uv_max=7.2,
                    wind_gust_max=13.0,
                )
            }
        ),
        ai_service=AiService(primary=ai_client),
    )

    summary = await service.build_morning_forecast_summary()

    assert summary == "Утром ясно, днём возможен дождь, SPF пригодится."
    assert ai_client.last_prompt is not None
    assert "daily_uv_index_max" in ai_client.last_prompt
    assert "день" in ai_client.last_prompt


@pytest.mark.asyncio
async def test_weather_service_morning_fallback_mentions_rain_wind_and_spf():
    service = WeatherService(
        config_repo=InMemoryConfigRepo(["Minsk"]),
        weather_client=StubWeatherClient(
            forecasts={
                "Minsk": _forecast(
                    "Minsk",
                    afternoon=_slot("день", 18, 80, 5.0, 14.0, 7.0, "дождь"),
                    uv_max=7.0,
                    wind_gust_max=14.0,
                )
            }
        ),
        ai_service=AiService(primary=FailingAiClient()),
    )

    summary = await service.build_morning_forecast_summary()

    assert "Дождь вероятнее" in summary
    assert "Ветрено" in summary
    assert "SPF" in summary


@pytest.mark.asyncio
async def test_weather_service_builds_severe_alert_messages():
    service = WeatherService(
        config_repo=InMemoryConfigRepo(["Minsk"]),
        weather_client=StubWeatherClient(
            forecasts={
                "Minsk": _forecast(
                    "Minsk",
                    alerts=[
                        SevereWeatherAlert(
                            city="Minsk",
                            emoji="⛈️",
                            title="Гроза",
                            details="Днём возможна гроза, лучше быть осторожнее на улице.",
                        )
                    ],
                )
            }
        ),
        ai_service=AiService(primary=RecordingAiClient()),
    )

    alerts = await service.build_severe_weather_alerts()

    assert len(alerts) == 1
    assert "⛈️" in alerts[0]
    assert "Minsk" in alerts[0]
