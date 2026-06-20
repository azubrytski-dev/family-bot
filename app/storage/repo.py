from __future__ import annotations

from typing import Iterable, Protocol

from app.core.models import ChatRecord, SchedulerJob


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
