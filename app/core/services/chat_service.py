from __future__ import annotations

from typing import Iterable

from app.core.models import ChatRecord
from app.storage.repo import ChatRegistryRepository


class ChatRegistryService:
    def __init__(self, repo: ChatRegistryRepository) -> None:
        self._repo = repo

    async def record_chat_seen(
        self,
        chat_id: int,
        title: str | None,
        chat_type: str,
    ) -> None:
        await self._repo.upsert_chat(chat_id=chat_id, title=title, chat_type=chat_type)

    async def get_approved_chats(self) -> Iterable[ChatRecord]:
        return await self._repo.list_approved_chats()

    async def is_chat_approved(self, chat_id: int) -> bool:
        return await self._repo.is_chat_approved(chat_id)

    async def is_chat_test_allowed(self, chat_id: int) -> bool:
        return await self._repo.is_chat_test_allowed(chat_id)

    async def mark_chat_removed(self, chat_id: int) -> None:
        await self._repo.mark_chat_removed(chat_id)

    async def migrate_chat(self, old_chat_id: int, new_chat_id: int) -> None:
        await self._repo.migrate_chat(old_chat_id, new_chat_id)
