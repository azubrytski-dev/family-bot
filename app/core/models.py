from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatRecord:
    chat_id: int
    title: str | None
    chat_type: str
    is_active: bool
    is_approved: bool
    allow_test: bool
    removed_at: datetime | None


@dataclass
class SchedulerJob:
    job_key: str
    job_type: str
    cron_hour: int
    cron_minute: int
    timezone_name: str
    chat_id: int | None
    enabled: bool


@dataclass
class WeatherObservation:
    city: str
    latitude: float
    longitude: float
    temperature_c: float
    apparent_temperature_c: float
    condition_code: int
    condition_text: str
    wind_speed_km_h: float


@dataclass
class WeatherTimeSlot:
    label: str
    time_iso: str
    temperature_c: float
    apparent_temperature_c: float
    precipitation_probability: int
    precipitation_mm: float
    weather_code: int
    weather_text: str
    wind_speed_km_h: float
    wind_gust_km_h: float
    uv_index: float


@dataclass
class SevereWeatherAlert:
    city: str
    emoji: str
    title: str
    details: str


@dataclass
class WeatherForecast:
    current: WeatherObservation
    morning: WeatherTimeSlot
    afternoon: WeatherTimeSlot
    evening: WeatherTimeSlot
    daily_uv_index_max: float
    daily_precipitation_probability_max: int
    daily_wind_gust_max_km_h: float
    severe_alerts: list[SevereWeatherAlert]
