from __future__ import annotations

from typing import Iterable, Protocol

from datetime import date, datetime
from typing import Sequence

from app.core.models import ChatRecord, ChatSession, SchedulerJob, SessionMessage


class ChatRegistryRepository(Protocol):
    async def upsert_chat(
        self,
        chat_id: int,
        title: str | None,
        chat_type: str,
    ) -> None: ...

    async def list_approved_chats(self) -> Iterable[ChatRecord]: ...

    async def is_chat_approved(self, chat_id: int) -> bool: ...

    async def is_chat_test_allowed(self, chat_id: int) -> bool: ...

    async def mark_chat_removed(self, chat_id: int) -> None: ...

    async def migrate_chat(self, old_chat_id: int, new_chat_id: int) -> None: ...


class SchedulerJobRepository(Protocol):
    async def list_enabled_jobs(self) -> Iterable[SchedulerJob]: ...


class AppConfigRepository(Protocol):
    async def list_enabled_values(self, parameter: str) -> Iterable[str]: ...


class SessionMemoryRepository(Protocol):
    async def get_open_session(self, chat_id: int) -> ChatSession | None: ...

    async def create_session(
        self,
        chat_id: int,
        local_date: date,
        started_at_utc: datetime,
        expires_at_utc: datetime,
    ) -> ChatSession: ...

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
    ) -> None: ...

    async def list_expired_open_sessions(self, as_of_utc: datetime) -> Sequence[ChatSession]: ...

    async def list_session_messages(self, session_id: int) -> Sequence[SessionMessage]: ...

    async def archive_session(
        self,
        *,
        session_id: int,
        completed_at_utc: datetime,
        summary_text: str,
    ) -> None: ...
