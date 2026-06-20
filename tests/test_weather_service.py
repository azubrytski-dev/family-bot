from __future__ import annotations

import pytest

from app.core.models import WeatherObservation
from app.core.services.ai_service import AiService
from app.core.services.weather_service import WeatherService


class InMemoryConfigRepo:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    async def list_enabled_values(self, parameter: str) -> list[str]:
        assert parameter == "weather.city"
        return list(self._values)


class StubWeatherClient:
    def __init__(self, responses: dict[str, WeatherObservation | Exception]) -> None:
        self._responses = responses

    async def fetch_current_weather(self, city_name: str) -> WeatherObservation:
        result = self._responses[city_name]
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


@pytest.mark.asyncio
async def test_weather_service_returns_ai_summary_for_two_cities():
    ai_client = RecordingAiClient(reply="В Минске прохладно, а в Тбилиси теплее.")
    service = WeatherService(
        config_repo=InMemoryConfigRepo(["Minsk", "Tbilisi"]),
        weather_client=StubWeatherClient(
            {
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
            {
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
        weather_client=StubWeatherClient({"Minsk": _observation("Minsk", 3, 1, "пасмурно")}),
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
            {
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
        weather_client=StubWeatherClient({}),
        ai_service=AiService(primary=RecordingAiClient()),
    )

    summary = await service.build_weather_summary()

    assert "weather.city" in summary
