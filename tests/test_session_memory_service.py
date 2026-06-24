from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

import pytest

from app.core.models import ChatSession, SessionMessage
from app.core.services.session_memory_service import (
    BOT_SESSION_DISPLAY_NAME,
    BOT_SESSION_USER_ID,
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

    async def list_completed_sessions_for_date(
        self,
        *,
        chat_id: int,
        local_date: date,
    ) -> list[ChatSession]:
        return [
            session
            for session in self.sessions.values()
            if session.chat_id == chat_id and session.local_date == local_date and session.status == "completed"
        ]


class DummySummaryGenerator:
    def __init__(self, response: str = "Саша и Андрей обсуждали планы на день.") -> None:
        self.response = response
        self.calls: list[tuple[datetime, datetime, list[SessionMessage]]] = []

    async def generate_session_summary(
        self,
        *,
        started_at_utc: datetime,
        completed_at_utc: datetime,
        messages: Sequence[SessionMessage],
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
        message_text=" \n  Привет   \n\n   " + ("x" * 2100) + "   ",
        message_ts_utc=ts,
        is_reply_to_bot=True,
    )

    session = await repo.get_open_session(10)
    assert session is not None
    assert session.local_date.isoformat() == "2026-06-23"
    messages = await repo.list_session_messages(session.id)
    assert len(messages) == 1
    assert messages[0].message_text.startswith("Привет ")
    assert len(messages[0].message_text) == 2000
    assert "\n" not in messages[0].message_text
    assert "  " not in messages[0].message_text
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
async def test_record_message_preserves_full_weather_text_with_compact_whitespace() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    weather_text = (
        "24 июня 2026 года.\n\n"
        "Сегодня ожидается спокойный и пасмурный день в Минске и Тбилиси.  \n\n"
        "Минск: Утром +15°C, ветер 12 км/ч.  \n"
        "Тбилиси: Днём +20°C, ветер 14 км/ч. 🌥️😊"
    )

    await service.record_bot_reply(
        chat_id=10,
        telegram_message_id=501,
        message_text=weather_text,
        message_ts_utc=datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc),
        bot_username="family_bot",
    )

    session = await repo.get_open_session(10)
    assert session is not None
    messages = await repo.list_session_messages(session.id)
    assert len(messages) == 1
    assert messages[0].message_text == (
        "24 июня 2026 года. Сегодня ожидается спокойный и пасмурный день в Минске и Тбилиси. "
        "Минск: Утром +15°C, ветер 12 км/ч. Тбилиси: Днём +20°C, ветер 14 км/ч. 🌥️😊"
    )


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


@pytest.mark.asyncio
async def test_record_bot_reply_uses_default_bot_identity() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    ts = datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc)
    await service.record_bot_reply(
        chat_id=10,
        telegram_message_id=501,
        message_text="Привет, я рядом.",
        message_ts_utc=ts,
        bot_username="family_bot",
    )

    session = await repo.get_open_session(10)
    assert session is not None
    messages = await repo.list_session_messages(session.id)
    assert len(messages) == 1
    assert messages[0].user_id == BOT_SESSION_USER_ID
    assert messages[0].display_name == BOT_SESSION_DISPLAY_NAME
    assert messages[0].username == "family_bot"
    assert messages[0].is_reply_to_bot is False


@pytest.mark.asyncio
async def test_get_yesterday_completed_summaries_uses_local_date_and_completed_sessions() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    repo.sessions[1] = ChatSession(
        id=1,
        chat_id=10,
        local_date=date(2026, 6, 23),
        started_at_utc=datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc),
        completed_at_utc=datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc),
        status="completed",
        message_count=2,
        summary_text="Вчера обсуждали планы и прогулку с Малышом.",
    )
    repo.sessions[2] = ChatSession(
        id=2,
        chat_id=10,
        local_date=date(2026, 6, 24),
        started_at_utc=datetime(2026, 6, 24, 8, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 24, 14, 0, tzinfo=timezone.utc),
        completed_at_utc=datetime(2026, 6, 24, 14, 0, tzinfo=timezone.utc),
        status="completed",
        message_count=1,
        summary_text="Сегодня были домашние дела.",
    )

    context = await service.get_yesterday_completed_summaries(
        chat_id=10,
        as_of_utc=datetime(2026, 6, 24, 6, 0, tzinfo=timezone.utc),
    )

    assert context.local_date == date(2026, 6, 23)
    assert context.summaries == ["Вчера обсуждали планы и прогулку с Малышом."]


@pytest.mark.asyncio
async def test_get_yesterday_completed_summaries_uses_minsk_day_boundary() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    repo.sessions[1] = ChatSession(
        id=1,
        chat_id=10,
        local_date=date(2026, 6, 23),
        started_at_utc=datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc),
        completed_at_utc=datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc),
        status="completed",
        message_count=1,
        summary_text="В Минске это ещё вчерашняя сводка.",
    )

    context = await service.get_yesterday_completed_summaries(
        chat_id=10,
        as_of_utc=datetime(2026, 6, 23, 21, 30, tzinfo=timezone.utc),
    )

    assert context.local_date == date(2026, 6, 23)
    assert context.summaries == ["В Минске это ещё вчерашняя сводка."]


@pytest.mark.asyncio
async def test_get_test_morning_summaries_uses_open_session_preview_when_yesterday_is_empty() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator(response="Сегодня обсуждали планы на утро и домашние дела.")
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    repo.sessions[1] = ChatSession(
        id=1,
        chat_id=10,
        local_date=date(2026, 6, 24),
        started_at_utc=datetime(2026, 6, 24, 14, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 24, 20, 0, tzinfo=timezone.utc),
        completed_at_utc=None,
        status="open",
        message_count=2,
        summary_text=None,
    )
    repo.messages[1] = [
        SessionMessage(
            id=1,
            session_id=1,
            chat_id=10,
            telegram_message_id=101,
            user_id=501,
            username="andrei",
            display_name="Andrei",
            message_text="Надо завтра встать пораньше.",
            message_ts_utc=datetime(2026, 6, 24, 15, 0, tzinfo=timezone.utc),
            local_date=date(2026, 6, 24),
            is_reply_to_bot=False,
        )
    ]

    context = await service.get_test_morning_summaries(
        chat_id=10,
        as_of_utc=datetime(2026, 6, 24, 18, 0, tzinfo=timezone.utc),
    )

    assert context.local_date == date(2026, 6, 24)
    assert context.summaries == ["Сегодня обсуждали планы на утро и домашние дела."]


@pytest.mark.asyncio
async def test_get_evening_summaries_combines_yesterday_today_and_open_preview() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator(response="Ещё успели обсудить вечерние дела.")
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    repo.sessions[1] = ChatSession(
        id=1,
        chat_id=10,
        local_date=date(2026, 6, 23),
        started_at_utc=datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc),
        completed_at_utc=datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc),
        status="completed",
        message_count=1,
        summary_text="Вчера обсуждали планы на завтра.",
    )
    repo.sessions[2] = ChatSession(
        id=2,
        chat_id=10,
        local_date=date(2026, 6, 24),
        started_at_utc=datetime(2026, 6, 24, 8, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 24, 14, 0, tzinfo=timezone.utc),
        completed_at_utc=datetime(2026, 6, 24, 14, 0, tzinfo=timezone.utc),
        status="completed",
        message_count=1,
        summary_text="Сегодня уже сходили по делам.",
    )
    repo.sessions[3] = ChatSession(
        id=3,
        chat_id=10,
        local_date=date(2026, 6, 24),
        started_at_utc=datetime(2026, 6, 24, 15, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 24, 21, 0, tzinfo=timezone.utc),
        completed_at_utc=None,
        status="open",
        message_count=1,
        summary_text=None,
    )
    repo.messages[3] = [
        SessionMessage(
            id=1,
            session_id=3,
            chat_id=10,
            telegram_message_id=101,
            user_id=501,
            username="andrei",
            display_name="Andrei",
            message_text="Ещё надо не забыть про вечернюю прогулку.",
            message_ts_utc=datetime(2026, 6, 24, 16, 0, tzinfo=timezone.utc),
            local_date=date(2026, 6, 24),
            is_reply_to_bot=False,
        )
    ]

    context = await service.get_evening_summaries(
        chat_id=10,
        as_of_utc=datetime(2026, 6, 24, 18, 0, tzinfo=timezone.utc),
    )

    assert context.yesterday_date == date(2026, 6, 23)
    assert context.today_date == date(2026, 6, 24)
    assert context.yesterday_summaries == ["Вчера обсуждали планы на завтра."]
    assert context.today_summaries == [
        "Сегодня уже сходили по делам.",
        "Ещё успели обсудить вечерние дела.",
    ]


@pytest.mark.asyncio
async def test_build_reply_context_uses_recent_summaries_and_open_session_messages() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    repo.sessions[1] = ChatSession(
        id=1,
        chat_id=10,
        local_date=date(2026, 6, 23),
        started_at_utc=datetime(2026, 6, 23, 8, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc),
        completed_at_utc=datetime(2026, 6, 23, 14, 0, tzinfo=timezone.utc),
        status="completed",
        message_count=1,
        summary_text="Вчера обсудили планы и прогулку с Малышом.",
    )
    repo.sessions[2] = ChatSession(
        id=2,
        chat_id=10,
        local_date=date(2026, 6, 24),
        started_at_utc=datetime(2026, 6, 24, 8, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 24, 14, 0, tzinfo=timezone.utc),
        completed_at_utc=datetime(2026, 6, 24, 14, 0, tzinfo=timezone.utc),
        status="completed",
        message_count=1,
        summary_text="Сегодня вспомнили про Луника.",
    )
    repo.sessions[3] = ChatSession(
        id=3,
        chat_id=10,
        local_date=date(2026, 6, 24),
        started_at_utc=datetime(2026, 6, 24, 15, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 24, 21, 0, tzinfo=timezone.utc),
        completed_at_utc=None,
        status="open",
        message_count=2,
        summary_text=None,
    )
    repo.messages[3] = [
        SessionMessage(
            id=1,
            session_id=3,
            chat_id=10,
            telegram_message_id=201,
            user_id=BOT_SESSION_USER_ID,
            username="family_bot",
            display_name=BOT_SESSION_DISPLAY_NAME,
            message_text="Привет! Как у вас дела?",
            message_ts_utc=datetime(2026, 6, 24, 15, 10, tzinfo=timezone.utc),
            local_date=date(2026, 6, 24),
            is_reply_to_bot=False,
        ),
        SessionMessage(
            id=2,
            session_id=3,
            chat_id=10,
            telegram_message_id=202,
            user_id=501,
            username="andrei",
            display_name="Andrei",
            message_text="Подскажи про вечернюю прогулку.",
            message_ts_utc=datetime(2026, 6, 24, 15, 12, tzinfo=timezone.utc),
            local_date=date(2026, 6, 24),
            is_reply_to_bot=True,
        ),
    ]

    context = await service.build_reply_context(
        chat_id=10,
        author_user_id=501,
        author_name="Andrei",
        message_text="А что лучше взять с собой?",
        reply_to_message_text="Привет! Как у вас дела?",
        as_of_utc=datetime(2026, 6, 24, 15, 15, tzinfo=timezone.utc),
    )

    assert "Автор: Andrei" in context
    assert "Текущее сообщение: А что лучше взять с собой?" in context
    assert "Ответ на сообщение бота: Привет! Как у вас дела?" in context
    assert "Недавние сводки сессий:" in context
    assert "2026-06-23: Вчера обсудили планы и прогулку с Малышом." in context
    assert "2026-06-24: Сегодня вспомнили про Луника." in context
    assert "Последние сообщения автора:" in context
    assert "Подскажи про вечернюю прогулку." in context
    assert "Недавний контекст текущей сессии:" in context
    assert "Family Bot" in context
    assert "reply_to_bot=yes" in context
    assert "Подскажи про вечернюю прогулку." in context


@pytest.mark.asyncio
async def test_build_reply_context_surfaces_latest_bot_weather_message() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    repo.sessions[1] = ChatSession(
        id=1,
        chat_id=10,
        local_date=date(2026, 6, 24),
        started_at_utc=datetime(2026, 6, 24, 20, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc),
        completed_at_utc=None,
        status="open",
        message_count=3,
        summary_text=None,
    )
    repo.messages[1] = [
        SessionMessage(
            id=1,
            session_id=1,
            chat_id=10,
            telegram_message_id=301,
            user_id=BOT_SESSION_USER_ID,
            username="family_bot",
            display_name=BOT_SESSION_DISPLAY_NAME,
            message_text=(
                "24 июня 2026 года. В Тбилиси утром 23°C с ветром 13.2 км/ч, "
                "днём 30°C и сильным ветром 18.8 км/ч, вечером 27°C, ветер 25.1 км/ч."
            ),
            message_ts_utc=datetime(2026, 6, 24, 20, 30, tzinfo=timezone.utc),
            local_date=date(2026, 6, 24),
            is_reply_to_bot=False,
        ),
        SessionMessage(
            id=2,
            session_id=1,
            chat_id=10,
            telegram_message_id=302,
            user_id=501,
            username="andrei",
            display_name="Andrei",
            message_text="Как там погода и как ветер в Тбилиси сегодня?",
            message_ts_utc=datetime(2026, 6, 24, 20, 31, tzinfo=timezone.utc),
            local_date=date(2026, 6, 24),
            is_reply_to_bot=False,
        ),
    ]

    context = await service.build_reply_context(
        chat_id=10,
        author_user_id=501,
        author_name="Andrei",
        message_text="А какой ветер точно?",
        reply_to_message_text=None,
        as_of_utc=datetime(2026, 6, 24, 20, 32, tzinfo=timezone.utc),
    )

    assert "Последняя погодная сводка бота:" in context
    assert "ветром 18.8 км/ч" in context
    assert "ветер 25.1 км/ч" in context


@pytest.mark.asyncio
async def test_build_reply_context_skips_author_section_without_author_id() -> None:
    repo = InMemorySessionRepo()
    summary_generator = DummySummaryGenerator()
    service = SessionMemoryService(repo=repo, summary_generator=summary_generator, tz_name="Europe/Minsk")

    repo.sessions[1] = ChatSession(
        id=1,
        chat_id=10,
        local_date=date(2026, 6, 24),
        started_at_utc=datetime(2026, 6, 24, 15, 0, tzinfo=timezone.utc),
        expires_at_utc=datetime(2026, 6, 24, 21, 0, tzinfo=timezone.utc),
        completed_at_utc=None,
        status="open",
        message_count=1,
        summary_text=None,
    )
    repo.messages[1] = [
        SessionMessage(
            id=1,
            session_id=1,
            chat_id=10,
            telegram_message_id=201,
            user_id=501,
            username="andrei",
            display_name="Andrei",
            message_text="Сегодня ел борщ.",
            message_ts_utc=datetime(2026, 6, 24, 15, 10, tzinfo=timezone.utc),
            local_date=date(2026, 6, 24),
            is_reply_to_bot=False,
        ),
    ]

    context = await service.build_reply_context(
        chat_id=10,
        author_user_id=None,
        author_name="Andrei",
        message_text="Как тебе мой ужин?",
        reply_to_message_text=None,
        as_of_utc=datetime(2026, 6, 24, 15, 15, tzinfo=timezone.utc),
    )

    assert "Последние сообщения автора:" not in context
