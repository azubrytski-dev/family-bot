from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Protocol

from app.core.config import AppConfig
from app.core.models import WeatherSnapshot
from app.integrations.weather.client import WeatherApiClient, WeatherReading
from app.storage.repo import WeatherRepository


class WeatherClientProtocol(Protocol):
    async def get_current(self, city: str) -> WeatherReading | None: ...


@dataclass
class WeatherComparison:
    city: str
    today: WeatherSnapshot | None
    yesterday: WeatherSnapshot | None
    week_ago: WeatherSnapshot | None


class WeatherService:
    def __init__(
        self,
        config: AppConfig,
        repo: WeatherRepository,
        client: WeatherClientProtocol,
    ) -> None:
        self._config = config
        self._repo = repo
        self._client = client

    async def collect_daily_snapshots(self, today: date | None = None) -> None:
        """
        Fetch current weather for all configured cities and upsert daily snapshots.
        """
        if today is None:
            today = date.today()

        for city in self._config.weather_cities:
            reading = await self._client.get_current(city)
            if reading is None:
                continue
            snapshot = WeatherSnapshot(
                city=city,
                snapshot_date=today,
                temperature=reading.temperature,
                feels_like=reading.feels_like,
                condition=reading.condition,
                wind_speed=reading.wind_speed,
                raw_payload=reading.raw_payload,
            )
            await self._repo.store_snapshot(snapshot)

    async def get_city_comparison(self, city: str, today: date | None = None) -> WeatherComparison:
        if today is None:
            today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        today_snap = await self._repo.get_snapshot(city, today)
        y_snap = await self._repo.get_snapshot(city, yesterday)
        w_snap = await self._repo.get_snapshot(city, week_ago)

        return WeatherComparison(
            city=city,
            today=today_snap,
            yesterday=y_snap,
            week_ago=w_snap,
        )

    async def get_info_summary(self, today: date | None = None) -> str:
        """
        Build compact Russian summary suitable for /info.

        Strategy:
        - Try to ensure we have today's snapshots by fetching from the API.
        - If live fetch fails, fall back to the latest stored snapshot up to today.
        - If there is no data at all, return a short fallback message.
        """
        if today is None:
            today = date.today()

        cities = list(self._config.weather_cities)
        if not cities:
            return "Погода: города для отслеживания пока не настроены."

        snapshots: list[WeatherSnapshot] = []

        for city in cities:
            # First, try to get today's snapshot.
            snap = await self._repo.get_snapshot(city, today)
            if snap is None:
                # Try to fetch live and store.
                reading = await self._client.get_current(city)
                if reading is not None:
                    snap = WeatherSnapshot(
                        city=city,
                        snapshot_date=today,
                        temperature=reading.temperature,
                        feels_like=reading.feels_like,
                        condition=reading.condition,
                        wind_speed=reading.wind_speed,
                        raw_payload=reading.raw_payload,
                    )
                    await self._repo.store_snapshot(snap)

            if snap is None:
                # Last resort: use latest snapshot up to today, if any.
                snap = await self._repo.get_latest_snapshot_up_to(city, today)

            if snap is not None:
                snapshots.append(snap)

        if not snapshots:
            return "Погода: актуальные данные пока недоступны."

        return format_weather_summary(snapshots)


def format_weather_summary(snapshots: Iterable[WeatherSnapshot]) -> str:
    lines = ["Погода:"]
    for snap in snapshots:
        temp_part = "нет данных"
        if snap.temperature is not None:
            temp_val = f"{snap.temperature:.0f}°C"
            temp_part = temp_val

        cond = snap.condition or "без описания"
        lines.append(f"- {snap.city}: {temp_part}, {cond}")

    return "\n".join(lines)

