from __future__ import annotations

import httpx


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=20.0)

    async def generate_text(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self._api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text.strip()
        except (KeyError, IndexError):
            raise ValueError("Invalid response from Gemini API")

    async def aclose(self) -> None:
        await self._client.aclose()

