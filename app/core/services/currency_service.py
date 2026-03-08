from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, Protocol, Tuple

from app.core.models import CurrencyRate
from app.integrations.rates.client import RateReading, RatesApiClient
from app.storage.repo import CurrencyRepository


class RatesClientProtocol(Protocol):
    async def get_rates(
        self,
        base: str,
        targets: Iterable[str],
    ) -> Dict[str, RateReading] | None: ...


@dataclass
class RateComparison:
    base_currency: str
    target_currency: str
    today: CurrencyRate | None
    yesterday: CurrencyRate | None
    week_ago: CurrencyRate | None


class CurrencyService:
    """
    Orchestrates collection and comparison of daily FX rates.
    """

    def __init__(
        self,
        repo: CurrencyRepository,
        client: RatesClientProtocol,
    ) -> None:
        self._repo = repo
        self._client = client

    @property
    def pairs(self) -> Tuple[Tuple[str, str], ...]:
        # Fixed set for MVP, as requested.
        return (
            ("EUR", "GEL"),
            ("USD", "GEL"),
            ("RUB", "GEL"),
            ("EUR", "BYN"),
            ("USD", "BYN"),
            ("RUB", "BYN"),
        )

    async def collect_daily_rates(self, today: date | None = None) -> None:
        """
        Fetch and store today's rates for all required pairs.
        """
        if today is None:
            today = date.today()

        # Group by base currency for efficient API calls.
        by_base: Dict[str, set[str]] = {}
        for base, target in self.pairs:
            by_base.setdefault(base, set()).add(target)

        for base, targets in by_base.items():
            readings = await self._client.get_rates(base, targets)
            if not readings:
                continue
            for target, reading in readings.items():
                rate = CurrencyRate(
                    base_currency=reading.base_currency,
                    target_currency=reading.target_currency,
                    rate_date=today,
                    rate=reading.rate,
                )
                await self._repo.store_rate(rate)

    async def get_rate_comparison(
        self,
        base: str,
        target: str,
        today: date | None = None,
    ) -> RateComparison:
        if today is None:
            today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        today_rate = await self._repo.get_rate(base, target, today)
        y_rate = await self._repo.get_rate(base, target, yesterday)
        w_rate = await self._repo.get_rate(base, target, week_ago)

        return RateComparison(
            base_currency=base,
            target_currency=target,
            today=today_rate,
            yesterday=y_rate,
            week_ago=w_rate,
        )

    async def get_info_summary(self, today: date | None = None) -> str:
        """
        Build compact Russian summary suitable for /info.

        Strategy:
        - Try to ensure we have today's rates by fetching from the API.
        - If live fetch fails, fall back to the latest stored rate up to today.
        - If there is no data at all, return a short fallback message.
        """
        if today is None:
            today = date.today()

        # Try to make sure today's data exists.
        await self.collect_daily_rates(today=today)

        lines = ["Курсы валют:"]
        any_data = False

        for base, target in self.pairs:
            today_rate = await self._repo.get_rate(base, target, today)
            if today_rate is None:
                today_rate = await self._repo.get_latest_rate_up_to(base, target, today)

            if today_rate is None:
                lines.append(f"- {base}/{target}: данных пока нет")
                continue

            any_data = True

            yesterday = today - timedelta(days=1)
            y_rate = await self._repo.get_latest_rate_up_to(base, target, yesterday)

            delta_str = " (без изменений ко вчера)"
            if y_rate is not None:
                delta = today_rate.rate - y_rate.rate
                if abs(delta) < 1e-6:
                    delta_str = " (без изменений ко вчера)"
                elif delta > 0:
                    delta_str = f" (+{delta:.4f} ко вчера)"
                else:
                    delta_str = f" ({delta:.4f} ко вчера)"

            lines.append(f"- {base}/{target}: {today_rate.rate:.4f}{delta_str}")

        if not any_data:
            return "Курсы валют: актуальные данные пока недоступны."

        return "\n".join(lines)

