from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    # If not provided, the bot is allowed in any chat.
    target_chat_id: int | None = Field(default=None, alias="TARGET_CHAT_ID")

    enable_scheduler: bool = Field(default=True, alias="ENABLE_SCHEDULER")
    enable_activity_tracking: bool = Field(default=True, alias="ENABLE_ACTIVITY_TRACKING")

    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-nano", alias="OPENAI_MODEL")

    postgres_url: str = Field(alias="POSTGRES_URL")

    tz_name: str = Field(default="Europe/Minsk", alias="TZ_NAME")

    auto_run_migrations: bool = Field(default=True, alias="AUTO_RUN_MIGRATIONS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig()  # type: ignore[call-arg]
