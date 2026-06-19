from __future__ import annotations

import pytest

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
    async def get_approved_chats(self):  # type: ignore[no-untyped-def]
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


@pytest.mark.asyncio
async def test_close_runtime_resources_closes_everything():
    bot = DummyBot()
    openai_client = DummyClosable()
    conn = DummyClosable()
    scheduler = DummyScheduler()

    await close_runtime_resources(
        bot=bot,  # type: ignore[arg-type]
        openai_client=openai_client,  # type: ignore[arg-type]
        conn=conn,  # type: ignore[arg-type]
        scheduler=scheduler,  # type: ignore[arg-type]
    )

    assert bot.session.closed is True
    assert openai_client.closed is True
    assert conn.closed is True
    assert scheduler.stopped is True
