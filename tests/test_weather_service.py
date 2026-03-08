from __future__ import annotations

from datetime import date

import pytest

from app.core.config import AppConfig
from app.core.models import WeatherSnapshot
from app.core.services.weather_service import WeatherService, format_weather_summary
from app.integrations.weather.client import WeatherReading


class InMemoryWeatherRepo:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, date], WeatherSnapshot] = {}

    async def store_snapshot(self, snapshot: WeatherSnapshot) -> None:
        self.snapshots[(snapshot.city, snapshot.snapshot_date)] = snapshot

    async def get_snapshot(self, city: str, day: date) -> WeatherSnapshot | None:
        return self.snapshots.get((city, day))

    async def get_latest_snapshot_up_to(self, city: str, day: date) -> WeatherSnapshot | None:
        candidates = [
            snap
            for (c, d), snap in self.snapshots.items()
            if c == city and d <= day
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda s: s.snapshot_date, reverse=True)[0]


class DummyWeatherClient:
    def __init__(self, reading: WeatherReading | None) -> None:
        self._reading = reading

    async def get_current(self, city: str) -> WeatherReading | None:
        return self._reading


def _make_config(monkeypatch) -> AppConfig:
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("WEATHER_CITIES", "Minsk, Tbilisi")
    return AppConfig()  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_collect_daily_snapshots(monkeypatch):
    cfg = _make_config(monkeypatch)
    today = date(2025, 1, 1)
    repo = InMemoryWeatherRepo()

    reading = WeatherReading(
        city="Minsk",
        temperature=5.0,
        feels_like=3.0,
        condition="ясно",
        wind_speed=2.5,
        raw_payload={},
    )
    client = DummyWeatherClient(reading)

    service = WeatherService(config=cfg, repo=repo, client=client)  # type: ignore[arg-type]
    await service.collect_daily_snapshots(today=today)

    snap = await repo.get_snapshot("Minsk", today)
    assert snap is not None
    assert snap.temperature == pytest.approx(5.0)
    assert snap.feels_like == pytest.approx(3.0)


def test_format_weather_summary():
    snaps = [
        WeatherSnapshot(
            city="Minsk",
            snapshot_date=date(2025, 1, 1),
            temperature=6.4,
            feels_like=5.0,
            condition="облачно",
            wind_speed=3.0,
            raw_payload=None,
        ),
        WeatherSnapshot(
            city="Tbilisi",
            snapshot_date=date(2025, 1, 1),
            temperature=None,
            feels_like=None,
            condition=None,
            wind_speed=None,
            raw_payload=None,
        ),
    ]
    text = format_weather_summary(snaps)

    assert "Погода:" in text
    assert "Minsk" in text
    assert "6" in text  # rounded temperature
    assert "Tbilisi" in text
    assert "нет данных" in text

