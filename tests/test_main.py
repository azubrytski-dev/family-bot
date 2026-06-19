from __future__ import annotations

import pytest

from app.main import send_startup_greetings


class DummyBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class DummyChatRegistryService:
    async def get_active_chats(self):  # type: ignore[no-untyped-def]
        return [
            type("Chat", (), {"chat_id": 101})(),
            type("Chat", (), {"chat_id": 202})(),
        ]


@pytest.mark.asyncio
async def test_send_startup_greetings_sends_to_all_known_chats():
    bot = DummyBot()
    service = DummyChatRegistryService()

    await send_startup_greetings(bot, service)  # type: ignore[arg-type]

    assert [chat_id for chat_id, _ in bot.sent] == [101, 202]
