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
