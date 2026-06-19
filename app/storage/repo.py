from __future__ import annotations

from typing import Iterable, Protocol

from app.core.models import SchedulerJob


class ChatRegistryRepository(Protocol):
    async def upsert_chat(
        self,
        chat_id: int,
        title: str | None,
        chat_type: str,
    ) -> None: ...


class SchedulerJobRepository(Protocol):
    async def list_enabled_jobs(self) -> Iterable[SchedulerJob]: ...
