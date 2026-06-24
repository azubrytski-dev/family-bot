# Implementation: family-session-memory-summary-feature

## Working Notes

- Target files:
  - `app/storage/migrations/0007_add_chat_session_memory.sql`
  - `app/storage/repo.py`
  - `app/storage/pg_repo.py`
  - `app/core/models.py`
  - `app/core/services/session_memory_service.py`
  - `app/core/services/ai_service.py`
  - `app/bot/scheduler.py`
  - `app/bot/handlers.py`
  - `app/main.py`
- Key assumptions:
  - A session stays open for 6 hours from its first stored message.
  - Raw session messages are deleted only after summary persistence succeeds.
  - Only plain text messages are stored for memory in this step; captions and non-text content are ignored.
  - Personal bot replies should use recent archived summaries plus the current open-session transcript, without introducing a separate long-term raw-message store for completed sessions.
- Risks to watch:
  - Session completion now runs both on message ingestion and via an internal scheduler housekeeping pass, which reduces idle-chat gaps but still relies on the process scheduler being alive.
  - Morning generation now forces an expired-session completion pass before reading yesterday's summaries, which is good for freshness but still depends on the same repository/archive path succeeding.
  - Evening generation now previews the current open session when today's context is not fully archived yet, which improves relevance but means the evening message may reflect transient same-day context.
  - Personal replies now depend on the same current-session transcript and archived-summary paths, so failures in session reads should keep falling back to the old inline mention context instead of breaking bot replies.

## Test Plan

- Unit tests to add/update:
  - `tests/test_session_memory_service.py`
  - `tests/test_ai_service.py`
  - `tests/test_repositories.py`
  - `tests/test_scheduler.py`
  - `tests/test_handlers.py`
- Commands to run:
  - `uv run pytest`
- Deterministic coverage now includes:
  - session completion after the 6-hour TTL boundary;
  - raw-message deletion after successful archive;
  - raw-message retention when summary generation fails before archive;
  - internal housekeeping completion for idle expired sessions;
  - reply-to-bot flag capture and reply-context shaping;
  - morning and evening prompt composition against archived summaries.
