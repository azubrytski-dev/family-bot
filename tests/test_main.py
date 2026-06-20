from __future__ import annotations

import pytest
from aiogram.exceptions import TelegramMigrateToChat

from app.main import close_runtime_resources, send_startup_greetings


class DummyBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.session = type("Session", (), {"closed": False, "close": self._close_session})()

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))

    async def _close_session(self) -> None:
        self.session.closed = True


class DummyClosable:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    async def close(self) -> None:
        self.closed = True


class DummyScheduler:
    def __init__(self) -> None:
        self.stopped = False

    def shutdown(self, wait: bool = False) -> None:
        self.stopped = True


class DummyChatRegistryService:
    def __init__(self) -> None:
        self.migrations: list[tuple[int, int]] = []

    async def get_approved_chats(self):  # type: ignore[no-untyped-def]
        return [
            type("Chat", (), {"chat_id": 101})(),
            type("Chat", (), {"chat_id": 202})(),
        ]

    async def migrate_chat(self, old_chat_id: int, new_chat_id: int) -> None:
        self.migrations.append((old_chat_id, new_chat_id))


class MigratingBot(DummyBot):
    async def send_message(self, chat_id: int, text: str) -> None:
        if chat_id == 101:
            raise TelegramMigrateToChat(method=object(), message="migrate", migrate_to_chat_id=-100101)  # type: ignore[arg-type]
        await super().send_message(chat_id, text)


@pytest.mark.asyncio
async def test_send_startup_greetings_sends_to_all_known_chats():
    bot = DummyBot()
    service = DummyChatRegistryService()

    await send_startup_greetings(bot, service)  # type: ignore[arg-type]

    assert [chat_id for chat_id, _ in bot.sent] == [101, 202]


@pytest.mark.asyncio
async def test_send_startup_greetings_migrates_group_chat_and_retries() -> None:
    bot = MigratingBot()
    service = DummyChatRegistryService()

    await send_startup_greetings(bot, service)  # type: ignore[arg-type]

    assert service.migrations == [(101, -100101)]
    assert [chat_id for chat_id, _ in bot.sent] == [-100101, 202]


@pytest.mark.asyncio
async def test_close_runtime_resources_closes_everything():
    bot = DummyBot()
    openai_client = DummyClosable()
    weather_client = DummyClosable()
    scheduler = DummyScheduler()

    await close_runtime_resources(
        bot=bot,  # type: ignore[arg-type]
        openai_client=openai_client,  # type: ignore[arg-type]
        weather_client=weather_client,  # type: ignore[arg-type]
        scheduler=scheduler,  # type: ignore[arg-type]
    )

    assert bot.session.closed is True
    assert openai_client.closed is True
    assert weather_client.closed is True
    assert scheduler.stopped is True
