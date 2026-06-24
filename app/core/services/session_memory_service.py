from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.models import ChatSession, SessionMessage
from app.storage.repo import SessionMemoryRepository


SESSION_TTL = timedelta(hours=6)
MESSAGE_TEXT_LIMIT = 100
SUMMARY_TEXT_LIMIT = 500
DEFAULT_TZ_NAME = "Europe/Minsk"


class SessionSummaryGenerator(Protocol):
    async def generate_session_summary(
        self,
        *,
        started_at_utc: datetime,
        completed_at_utc: datetime,
        messages: Sequence[SessionMessage],
    ) -> str: ...


@dataclass
class SessionCompletionResult:
    session_id: int
    chat_id: int
    summary_text: str
    message_count: int


def _resolve_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TZ_NAME)


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SessionMemoryService:
    def __init__(
        self,
        repo: SessionMemoryRepository,
        summary_generator: SessionSummaryGenerator,
        tz_name: str,
    ) -> None:
        self._repo = repo
        self._summary_generator = summary_generator
        self._tz = _resolve_timezone(tz_name)

    async def record_message(
        self,
        *,
        chat_id: int,
        telegram_message_id: int,
        user_id: int,
        username: str | None,
        display_name: str | None,
        message_text: str,
        message_ts_utc: datetime,
        is_reply_to_bot: bool,
    ) -> None:
        normalized_text = self._normalize_message_text(message_text)
        if not normalized_text:
            return

        normalized_ts = _normalize_utc(message_ts_utc)
        await self.complete_expired_sessions(as_of_utc=normalized_ts)

        session = await self._repo.get_open_session(chat_id)
        if session is None:
            session = await self._repo.create_session(
                chat_id=chat_id,
                local_date=self._local_date(normalized_ts),
                started_at_utc=normalized_ts,
                expires_at_utc=normalized_ts + SESSION_TTL,
            )

        await self._repo.add_message(
            chat_id=chat_id,
            session_id=session.id,
            telegram_message_id=telegram_message_id,
            user_id=user_id,
            username=username,
            display_name=display_name,
            message_text=normalized_text,
            message_ts_utc=normalized_ts,
            local_date=self._local_date(normalized_ts),
            is_reply_to_bot=is_reply_to_bot,
        )

    async def complete_expired_sessions(self, *, as_of_utc: datetime | None = None) -> list[SessionCompletionResult]:
        normalized_as_of = _normalize_utc(as_of_utc or datetime.now(timezone.utc))
        expired_sessions = await self._repo.list_expired_open_sessions(normalized_as_of)
        results: list[SessionCompletionResult] = []

        for session in expired_sessions:
            messages = list(await self._repo.list_session_messages(session.id))
            if not messages:
                continue
            summary_text = await self._summary_generator.generate_session_summary(
                started_at_utc=session.started_at_utc,
                completed_at_utc=normalized_as_of,
                messages=messages,
            )
            normalized_summary = self._normalize_summary_text(summary_text)
            await self._repo.archive_session(
                session_id=session.id,
                completed_at_utc=normalized_as_of,
                summary_text=normalized_summary,
            )
            results.append(
                SessionCompletionResult(
                    session_id=session.id,
                    chat_id=session.chat_id,
                    summary_text=normalized_summary,
                    message_count=len(messages),
                )
            )
        return results

    def _local_date(self, value: datetime) -> date:
        return value.astimezone(self._tz).date()

    @staticmethod
    def _normalize_message_text(text: str) -> str:
        return text.strip()[:MESSAGE_TEXT_LIMIT]

    @staticmethod
    def _normalize_summary_text(text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return "Короткая семейная сводка пока недоступна."
        return normalized[:SUMMARY_TEXT_LIMIT]
