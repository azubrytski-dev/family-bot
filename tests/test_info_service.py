from __future__ import annotations

from datetime import date

import pytest

from app.core.config import AppConfig
from app.core.services.currency_service import CurrencyService
from app.core.services.info_service import InfoService
from app.core.services.weather_service import WeatherService, format_weather_summary


def _make_config(monkeypatch) -> AppConfig:
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("WEATHER_CITIES", "Minsk")
    return AppConfig()  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_info_service_builds_summary_with_data(monkeypatch):
    cfg = _make_config(monkeypatch)
    today = date(2025, 1, 1)

    class DummyWeatherService:
        async def get_info_summary(self, today: date | None = None) -> str:
            return "Погода: тестовые данные."

    class DummyCurrencyService:
        async def get_info_summary(self, today: date | None = None) -> str:
            return "Курсы валют: тестовые данные."

    info = InfoService(
        weather_service=DummyWeatherService(),  # type: ignore[arg-type]
        currency_service=DummyCurrencyService(),  # type: ignore[arg-type]
    )
    summary = await info.build_summary(today)

    assert "Информация на сегодня" in summary
    assert "Погода: тестовые данные." in summary
    assert "Курсы валют: тестовые данные." in summary

