from __future__ import annotations

from datetime import date

from app.core.services.currency_service import CurrencyService
from app.core.services.weather_service import WeatherService


class InfoService:
    """
    Builds a short Russian /info summary combining weather and currency modules.
    """

    def __init__(
        self,
        weather_service: WeatherService,
        currency_service: CurrencyService,
    ) -> None:
        self._weather_service = weather_service
        self._currency_service = currency_service

    async def build_summary(self, today: date | None = None) -> str:
        if today is None:
            today = date.today()

        weather_block = await self._weather_service.get_info_summary(today)
        currency_block = await self._currency_service.get_info_summary(today)

        return (
            f"Информация на сегодня:\n\n"
            f"{weather_block}\n\n"
            f"{currency_block}"
        )

