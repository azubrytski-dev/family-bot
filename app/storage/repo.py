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

    async def list_active_chats(self) -> Iterable[ChatRecord]: ...


class SchedulerJobRepository(Protocol):
    async def list_enabled_jobs(self) -> Iterable[SchedulerJob]: ...
