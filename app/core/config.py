from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    # If not provided, the bot is allowed in any chat.
    target_chat_id: int | None = Field(default=None, alias="TARGET_CHAT_ID")

    # Raw CSV string from env; parsed via property below.
    weather_cities_raw: str = Field(default="", alias="WEATHER_CITIES")
    weather_api_key: str | None = Field(default=None, alias="WEATHER_API_KEY")
    weather_api_base_url: str = Field(
        default="https://api.openweathermap.org/data/2.5",
        alias="WEATHER_API_BASE_URL",
    )

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    postgres_url: str = Field(alias="POSTGRES_URL")

    rates_api_base_url: str = Field(
        default="https://api.exchangerate.host",
        alias="RATES_API_BASE_URL",
    )

    tz_name: str = Field(default="Europe/Minsk", alias="TZ_NAME")

    auto_run_migrations: bool = Field(default=True, alias="AUTO_RUN_MIGRATIONS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @property
    def weather_cities(self) -> List[str]:
        raw = self.weather_cities_raw
        if not raw:
            return []
        return [city.strip() for city in raw.split(",") if city.strip()]


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig()  # type: ignore[call-arg]

