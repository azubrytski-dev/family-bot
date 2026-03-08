from __future__ import annotations

from datetime import date

import pytest

from app.core.models import CurrencyRate
from app.core.services.currency_service import CurrencyService
from app.integrations.rates.client import RateReading


class InMemoryCurrencyRepo:
    def __init__(self) -> None:
        self.rates: dict[tuple[str, str, date], CurrencyRate] = {}

    async def store_rate(self, rate: CurrencyRate) -> None:
        key = (rate.base_currency, rate.target_currency, rate.rate_date)
        self.rates[key] = rate

    async def get_rate(
        self,
        base_currency: str,
        target_currency: str,
        day: date,
    ) -> CurrencyRate | None:
        return self.rates.get((base_currency, target_currency, day))

    async def get_latest_rate_up_to(
        self,
        base_currency: str,
        target_currency: str,
        day: date,
    ) -> CurrencyRate | None:
        candidates = [
            r
            for (b, t, d), r in self.rates.items()
            if b == base_currency and t == target_currency and d <= day
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda r: r.rate_date, reverse=True)[0]


class DummyRatesClient:
    def __init__(self, readings: dict[str, RateReading] | None) -> None:
        self._readings = readings

    async def get_rates(self, base: str, targets):
        return self._readings


@pytest.mark.asyncio
async def test_collect_daily_rates_and_summary():
    repo = InMemoryCurrencyRepo()
    today = date(2025, 1, 1)

    readings = {
        "BYN": RateReading(
            base_currency="USD",
            target_currency="BYN",
            rate=3.5,
            raw_payload={},
        )
    }
    client = DummyRatesClient(readings)

    service = CurrencyService(repo=repo, client=client)  # type: ignore[arg-type]

    await service.collect_daily_rates(today=today)

    stored = await repo.get_rate("USD", "BYN", today)
    assert stored is not None
    assert stored.rate == pytest.approx(3.5)

    # With only today's data, deltas should mention "без изменений".
    summary = await service.get_info_summary(today=today)
    assert "Курсы валют:" in summary
    assert "USD/BYN" in summary
    assert "без изменений" in summary

