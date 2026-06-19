from __future__ import annotations

import pytest

from app.core.services.ai_service import AiService, BASE_FAMILY_PROMPT


class DummyClient:
    def __init__(self) -> None:
        self.last_prompt: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        # Echo back a short fixed answer to simulate AI behavior.
        return "Привет, зубры! Я тут и готов помочь."


@pytest.mark.asyncio
async def test_reply_to_mention_uses_base_prompt():
    client = DummyClient()
    service = AiService(primary=client)

    reply = await service.reply_to_mention("Привет, бот!")

    assert "Привет" in reply
    assert client.last_prompt is not None
    assert BASE_FAMILY_PROMPT in client.last_prompt


