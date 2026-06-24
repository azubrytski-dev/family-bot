from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.models import ChatSession, SessionMessage
from app.core.services.session_memory_service import (
    SESSION_TTL,
    SessionMemoryService,
)


class InMemorySessionRepo:
    def __init__(self) -> None:
        self.next_session_id = 1
        self.next_message_id = 1
        self.sessions: dict[int, ChatSession] = {}
        self.messages: dict[int, list[SessionMessage]] = {}

    async def get_open_session(self, chat_id: int) -> ChatSession | None:
        for session in self.sessions.values():
            if session.chat_id == chat_id and session.status == "open":
                return session
        return None

    async def create_session(
        self,
        chat_id: int,
        local_date: date,
        started_at_utc: datetime,
        expires_at_utc: datetime,
    ) -> ChatSession:
        session = ChatSession(
            id=self.next_session_id,
            chat_id=chat_id,
            local_date=local_date,
            started_at_utc=started_at_utc,
            expires_at_utc=expires_at_utc,
            completed_at_utc=None,
            status="open",
            message_count=0,
            summary_text=None,
        )
        self.sessions[session.id] = session
        self.messages[session.id] = []
        self.next_session_id += 1
        return session

    async def add_message(
        self,
        *,
        chat_id: int,
        session_id: int,
        telegram_message_id: int,
        user_id: int,
        username: str | None,
        display_name: str | None,
        message_text: str,
        message_ts_utc: datetime,
        local_date: date,
        is_reply_to_bot: bool,
    ) -> None:
        message = SessionMessage(
            id=self.next_message_id,
            session_id=session_id,
            chat_id=chat_id,
            telegram_message_id=telegram_message_id,
            user_id=user_id,
            username=username,
            display_name=display_name,
            message_text=message_text,
            message_ts_utc=message_ts_utc,
            local_date=local_date,
            is_reply_to_bot=is_reply_to_bot,
        )
        self.next_message_id += 1
        self.messages[session_id].append(message)
        session = self.sessions[session_id]
        self.sessions[session_id] = replace(session, message_count=len(self.messages[session_id]))

    async def list_expired_open_sessions(self, as_of_utc: datetime) -> list[ChatSession]:
        return [
            session
            for session in self.sessions.values()
            if session.status == "open" and session.expires_at_utc <= as_of_utc
        ]

    async def list_session_messages(self, session_id: int) -> list[SessionMessage]:
        return list(self.messages.get(session_id, []))

    async def archive_session(
        self,
        *,
        session_id: int,
        completed_at_utc: datetime,
        summary_text: str,
    ) -> None:
        message_count = len(self.messages.get(session_id, []))
        session = self.sessions[session_id]
        self.sessions[session_id] = replace(
            session,
            completed_at_utc=completed_at_utc,
            status="completed",
            summary_text=summary_text,
            message_count=message_count,
        )
        self.messages[session_id] = []


class DummySummaryGenerator:
    def __init__(self, response: str = "Саша и Андрей обсуждали планы на день.") -> None:
        self.response = response
        self.calls: list[tuple[datetime, datetime, list[SessionMessage]]] = []

    async def generate_session_summary(
        self,
        *,
        started_at_utc: datetime,
        completed_at_utc: datetime,
        messages: list[SessionMessage],
    ) -> str:
        self.calls.append((started_at_utc, completed_at_utc, list(messages)))
        return self.response


@pytest.mark.asyncio
async def test_record_message_creates_session_and_trims_text() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    ts = datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc)
    await service.record_message(
        chat_id=10,
        telegram_message_id=77,
        user_id=501,
        username="andrei",
        display_name="Andrei",
        message_text="  " + ("x" * 140) + "  ",
        message_ts_utc=ts,
        is_reply_to_bot=True,
    )

    session = await repo.get_open_session(10)
    assert session is not None
    assert session.local_date.isoformat() == "2026-06-23"
    messages = await repo.list_session_messages(session.id)
    assert len(messages) == 1
    assert messages[0].message_text == "x" * 100
    assert messages[0].is_reply_to_bot is True
    assert messages[0].local_date.isoformat() == "2026-06-23"


@pytest.mark.asyncio
async def test_record_message_ignores_blank_text() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    await service.record_message(
        chat_id=10,
        telegram_message_id=77,
        user_id=501,
        username="andrei",
        display_name="Andrei",
        message_text="   ",
        message_ts_utc=datetime.now(timezone.utc),
        is_reply_to_bot=False,
    )

    assert repo.sessions == {}


@pytest.mark.asyncio
async def test_record_message_completes_expired_session_before_creating_next_one() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator(response="A" * 520)
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    start_ts = datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc)
    await service.record_message(
        chat_id=10,
        telegram_message_id=1,
        user_id=501,
        username="andrei",
        display_name="Andrei",
        message_text="Собираемся в поездку.",
        message_ts_utc=start_ts,
        is_reply_to_bot=False,
    )

    next_ts = start_ts + SESSION_TTL + timedelta(minutes=5)
    await service.record_message(
        chat_id=10,
        telegram_message_id=2,
        user_id=502,
        username="inna",
        display_name="Inna",
        message_text="Не забудьте документы.",
        message_ts_utc=next_ts,
        is_reply_to_bot=False,
    )

    assert len(summary_generator.calls) == 1
    first_session = repo.sessions[1]
    assert first_session.status == "completed"
    assert first_session.completed_at_utc == next_ts
    assert first_session.summary_text == "A" * 500
    assert repo.messages[1] == []

    second_session = await repo.get_open_session(10)
    assert second_session is not None
    assert second_session.id == 2
    messages = await repo.list_session_messages(second_session.id)
    assert [message.telegram_message_id for message in messages] == [2]


@pytest.mark.asyncio
async def test_invalid_timezone_falls_back_to_default() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Invalid/Timezone")

    ts = datetime(2026, 6, 22, 22, 30, tzinfo=timezone.utc)
    await service.record_message(
        chat_id=10,
        telegram_message_id=1,
        user_id=1,
        username=None,
        display_name="Alyona",
        message_text="Доброй ночи",
        message_ts_utc=ts,
        is_reply_to_bot=False,
    )

    session = await repo.get_open_session(10)
    assert session is not None
    assert session.local_date.isoformat() == "2026-06-23"
