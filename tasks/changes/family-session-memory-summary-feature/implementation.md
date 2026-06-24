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
  - Step 2 owns only the morning summary-consumption path; evening-message generation and personal-reply session context remain future work.
  - A session stays open for 6 hours from its first stored message.
  - Raw session messages are deleted only after summary persistence succeeds.
  - Only plain text messages are stored for memory in this step; captions and non-text content are ignored.
- Risks to watch:
  - Session completion is currently triggered during message recording, so idle chats will need a later scheduled completion path if no new messages arrive after expiry.
  - Morning generation now forces an expired-session completion pass before reading yesterday's summaries, which is good for freshness but still depends on the same repository/archive path succeeding.
  - Summary consumption for evening messages and personal replies is still deferred to later steps.

## Test Plan

- Unit tests to add/update:
  - `tests/test_session_memory_service.py`
  - `tests/test_ai_service.py`
  - `tests/test_repositories.py`
  - `tests/test_scheduler.py`
  - `tests/test_handlers.py`
- Commands to run:
  - `uv run pytest`
