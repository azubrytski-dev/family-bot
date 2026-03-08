from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable

import httpx


@dataclass
class RateReading:
    base_currency: str
    target_currency: str
    rate: float
    raw_payload: dict[str, Any] | None


class RatesClientError(Exception):
    pass


class RatesApiClient:
    """
    Minimal exchangerate.host client for daily FX rates.

    Base URL can be customized but defaults to https://api.exchangerate.host.
    API key is not required for basic usage.
    """

    def __init__(self, base_url: str = "https://api.exchangerate.host") -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=10.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_rates(
        self,
        base: str,
        targets: Iterable[str],
    ) -> Dict[str, RateReading] | None:
        """
        Fetch rates for a base currency against multiple targets.

        Returns mapping target_currency -> RateReading, or None on non-fatal error.
        """
        symbols = ",".join(sorted(set(targets)))
        params = {
            "base": base,
            "symbols": symbols,
        }
        try:
            resp = await self._client.get(f"{self._base_url}/latest", params=params)
        except httpx.RequestError:
            return None

        if resp.status_code != 200:
            return None

        data = resp.json()
        rates = data.get("rates") or {}
        result: Dict[str, RateReading] = {}
        for target, value in rates.items():
            try:
                rate_val = float(value)
            except (TypeError, ValueError):
                continue
            result[target] = RateReading(
                base_currency=base,
                target_currency=target,
                rate=rate_val,
                raw_payload=data,
            )
        return result

