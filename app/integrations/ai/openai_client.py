from __future__ import annotations

import logging

import httpx


class OpenAIClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=10.0)
        )
        self._logger = logging.getLogger(__name__)

    async def generate_text(self, prompt: str) -> str:
        return await self.generate_messages(
            system_prompt="You are a helpful assistant.",
            user_prompt=prompt,
        )

    async def generate_messages(self, system_prompt: str, user_prompt: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "max_tokens": 450,
            "temperature": 0.7,
        }
        self._logger.info("Calling OpenAI chat completions model=%s.", self._model)
        response = await self._client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"]
            return text.strip()
        except (KeyError, IndexError):
            raise ValueError("Invalid response from OpenAI API")

    async def aclose(self) -> None:
        await self._client.aclose()
