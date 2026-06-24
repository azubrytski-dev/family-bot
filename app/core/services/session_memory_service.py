from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re
from typing import Protocol, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.models import ChatSession, SessionMessage
from app.storage.repo import SessionMemoryRepository


SESSION_TTL = timedelta(hours=6)
MESSAGE_TEXT_LIMIT = 2000
SUMMARY_TEXT_LIMIT = 500
REPLY_CONTEXT_SUMMARY_LIMIT = 4
REPLY_CONTEXT_MESSAGE_LIMIT = 8
REPLY_CONTEXT_AUTHOR_MESSAGE_LIMIT = 3
DEFAULT_TZ_NAME = "Europe/Minsk"
BOT_SESSION_USER_ID = 0
BOT_SESSION_DISPLAY_NAME = "Family Bot"


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


@dataclass
class MorningSummaryContext:
    local_date: date
    summaries: list[str]


@dataclass
class EveningSummaryContext:
    yesterday_date: date
    today_date: date
    yesterday_summaries: list[str]
    today_summaries: list[str]


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

    async def record_bot_reply(
        self,
        *,
        chat_id: int,
        telegram_message_id: int,
        message_text: str,
        message_ts_utc: datetime,
        bot_username: str | None,
    ) -> None:
        await self.record_message(
            chat_id=chat_id,
            telegram_message_id=telegram_message_id,
            user_id=BOT_SESSION_USER_ID,
            username=bot_username,
            display_name=BOT_SESSION_DISPLAY_NAME,
            message_text=message_text,
            message_ts_utc=message_ts_utc,
            is_reply_to_bot=False,
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

    async def get_yesterday_completed_summaries(
        self,
        *,
        chat_id: int,
        as_of_utc: datetime | None = None,
    ) -> MorningSummaryContext:
        normalized_as_of = _normalize_utc(as_of_utc or datetime.now(timezone.utc))
        await self.complete_expired_sessions(as_of_utc=normalized_as_of)
        local_today = self._local_date(normalized_as_of)
        yesterday = local_today - timedelta(days=1)
        sessions = await self._repo.list_completed_sessions_for_date(chat_id=chat_id, local_date=yesterday)
        summaries = [session.summary_text.strip() for session in sessions if session.summary_text and session.summary_text.strip()]
        return MorningSummaryContext(local_date=yesterday, summaries=summaries)

    async def get_test_morning_summaries(
        self,
        *,
        chat_id: int,
        as_of_utc: datetime | None = None,
    ) -> MorningSummaryContext:
        normalized_as_of = _normalize_utc(as_of_utc or datetime.now(timezone.utc))
        yesterday_context = await self.get_yesterday_completed_summaries(
            chat_id=chat_id,
            as_of_utc=normalized_as_of,
        )
        if yesterday_context.summaries:
            return yesterday_context

        local_today = self._local_date(normalized_as_of)
        today_sessions = await self._repo.list_completed_sessions_for_date(chat_id=chat_id, local_date=local_today)
        today_summaries = [
            session.summary_text.strip()
            for session in today_sessions
            if session.summary_text and session.summary_text.strip()
        ]
        if today_summaries:
            return MorningSummaryContext(local_date=local_today, summaries=today_summaries)

        open_session = await self._repo.get_open_session(chat_id)
        if open_session is None:
            return MorningSummaryContext(local_date=local_today, summaries=[])

        messages = list(await self._repo.list_session_messages(open_session.id))
        if not messages:
            return MorningSummaryContext(local_date=local_today, summaries=[])

        preview_summary = await self._summary_generator.generate_session_summary(
            started_at_utc=open_session.started_at_utc,
            completed_at_utc=normalized_as_of,
            messages=messages,
        )
        normalized_summary = self._normalize_summary_text(preview_summary)
        return MorningSummaryContext(local_date=local_today, summaries=[normalized_summary])

    async def get_evening_summaries(
        self,
        *,
        chat_id: int,
        as_of_utc: datetime | None = None,
    ) -> EveningSummaryContext:
        normalized_as_of = _normalize_utc(as_of_utc or datetime.now(timezone.utc))
        await self.complete_expired_sessions(as_of_utc=normalized_as_of)
        local_today = self._local_date(normalized_as_of)
        yesterday = local_today - timedelta(days=1)

        yesterday_sessions = await self._repo.list_completed_sessions_for_date(chat_id=chat_id, local_date=yesterday)
        today_sessions = await self._repo.list_completed_sessions_for_date(chat_id=chat_id, local_date=local_today)

        yesterday_summaries = [
            session.summary_text.strip()
            for session in yesterday_sessions
            if session.summary_text and session.summary_text.strip()
        ]
        today_summaries = [
            session.summary_text.strip()
            for session in today_sessions
            if session.summary_text and session.summary_text.strip()
        ]

        open_session = await self._repo.get_open_session(chat_id)
        if open_session is not None and open_session.local_date == local_today:
            messages = list(await self._repo.list_session_messages(open_session.id))
            if messages:
                preview_summary = await self._summary_generator.generate_session_summary(
                    started_at_utc=open_session.started_at_utc,
                    completed_at_utc=normalized_as_of,
                    messages=messages,
                )
                normalized_preview = self._normalize_summary_text(preview_summary)
                if normalized_preview:
                    today_summaries.append(normalized_preview)

        return EveningSummaryContext(
            yesterday_date=yesterday,
            today_date=local_today,
            yesterday_summaries=yesterday_summaries,
            today_summaries=today_summaries,
        )

    async def build_reply_context(
        self,
        *,
        chat_id: int,
        author_user_id: int | None,
        author_name: str,
        message_text: str,
        reply_to_message_text: str | None,
        as_of_utc: datetime | None = None,
    ) -> str:
        normalized_as_of = _normalize_utc(as_of_utc or datetime.now(timezone.utc))
        await self.complete_expired_sessions(as_of_utc=normalized_as_of)
        local_today = self._local_date(normalized_as_of)
        yesterday = local_today - timedelta(days=1)

        sections = [
            f"Автор: {author_name}",
            f"Текущее сообщение: {self._normalize_message_text(message_text)}",
        ]
        normalized_reply = self._normalize_message_text(reply_to_message_text or "")
        if normalized_reply:
            sections.append(f"Ответ на сообщение бота: {normalized_reply}")

        summary_lines = await self._list_recent_summary_lines(
            chat_id=chat_id,
            local_dates=(yesterday, local_today),
        )
        if summary_lines:
            sections.append("Недавние сводки сессий:\n" + "\n".join(summary_lines))

        author_message_lines = await self._list_recent_author_messages(
            chat_id=chat_id,
            author_user_id=author_user_id,
            current_message_text=self._normalize_message_text(message_text),
        )
        if author_message_lines:
            sections.append("Последние сообщения автора:\n" + "\n".join(author_message_lines))

        latest_weather_message = await self._get_latest_bot_weather_message(chat_id=chat_id)
        if latest_weather_message:
            sections.append(f"Последняя погодная сводка бота:\n{latest_weather_message}")

        transcript_lines = await self._list_open_session_transcript(chat_id=chat_id)
        if transcript_lines:
            sections.append("Недавний контекст текущей сессии:\n" + "\n".join(transcript_lines))

        return "\n\n".join(section for section in sections if section.strip())

    def _local_date(self, value: datetime) -> date:
        return value.astimezone(self._tz).date()

    async def _list_recent_summary_lines(
        self,
        *,
        chat_id: int,
        local_dates: Sequence[date],
    ) -> list[str]:
        summary_lines: list[str] = []
        for local_date in local_dates:
            sessions = await self._repo.list_completed_sessions_for_date(chat_id=chat_id, local_date=local_date)
            for session in sessions:
                summary = (session.summary_text or "").strip()
                if not summary:
                    continue
                summary_lines.append(f"- {local_date.isoformat()}: {summary}")
                if len(summary_lines) >= REPLY_CONTEXT_SUMMARY_LIMIT:
                    return summary_lines
        return summary_lines

    async def _list_open_session_transcript(self, *, chat_id: int) -> list[str]:
        open_session = await self._repo.get_open_session(chat_id)
        if open_session is None:
            return []

        messages = list(await self._repo.list_session_messages(open_session.id))
        if not messages:
            return []

        transcript_lines: list[str] = []
        for message in messages[-REPLY_CONTEXT_MESSAGE_LIMIT:]:
            speaker = message.display_name or message.username or f"id:{message.user_id}"
            reply_flag = "yes" if message.is_reply_to_bot else "no"
            transcript_lines.append(
                f"- {message.message_ts_utc.isoformat()} | {speaker} | reply_to_bot={reply_flag} | {message.message_text}"
            )
        return transcript_lines

    async def _list_recent_author_messages(
        self,
        *,
        chat_id: int,
        author_user_id: int | None,
        current_message_text: str,
    ) -> list[str]:
        if author_user_id is None:
            return []

        open_session = await self._repo.get_open_session(chat_id)
        if open_session is None:
            return []

        messages = list(await self._repo.list_session_messages(open_session.id))
        if not messages:
            return []

        author_messages = [
            message
            for message in messages
            if message.user_id == author_user_id
            and message.message_text != current_message_text
        ]
        recent_messages = author_messages[-REPLY_CONTEXT_AUTHOR_MESSAGE_LIMIT:]
        return [f"- {message.message_text}" for message in recent_messages]

    async def _get_latest_bot_weather_message(self, *, chat_id: int) -> str | None:
        open_session = await self._repo.get_open_session(chat_id)
        if open_session is None:
            return None

        messages = list(await self._repo.list_session_messages(open_session.id))
        for message in reversed(messages):
            if message.user_id != BOT_SESSION_USER_ID:
                continue
            if self._looks_like_weather_message(message.message_text):
                return message.message_text
        return None

    @staticmethod
    def _looks_like_weather_message(text: str) -> bool:
        lowered = text.lower()
        weather_markers = (
            "погод",
            "ветер",
            "дожд",
            "uv",
            "spf",
            "°c",
            "минск",
            "тбилиси",
        )
        marker_hits = sum(1 for marker in weather_markers if marker in lowered)
        return marker_hits >= 2

    @staticmethod
    def _normalize_message_text(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        return normalized[:MESSAGE_TEXT_LIMIT]

    @staticmethod
    def _normalize_summary_text(text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return "Короткая семейная сводка пока недоступна."
        return normalized[:SUMMARY_TEXT_LIMIT]
