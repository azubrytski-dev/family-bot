# Implementation: simplify-to-ai-and-db-scheduler

## Working Notes

- Target files:
  - `app/main.py`
  - `app/bot/handlers.py`
  - `app/bot/scheduler.py`
  - `app/storage/repo.py`
  - `app/storage/pg_repo.py`
  - `app/storage/migrations/0001_init.sql`
- Key assumptions:
  - AI replies should be limited to direct bot interactions such as `@username` mentions or replies to the bot.
  - Scheduler job rows may omit `chat_id` and fall back to `TARGET_CHAT_ID`.
  - Fresh local environments are expected to bootstrap from the simplified current schema rather than replay legacy feature history.
- Risks to watch:
  - malformed scheduler job rows need to fail soft rather than break startup;
  - `.env` values can leak into tests unless explicitly disabled.

## Test Plan

- Unit tests to add/update:
  - scheduler setup tests for DB-defined jobs and missing-chat fallback behavior;
  - handler helper tests for AI trigger detection;
  - config regression checks around scheduler defaults;
  - repository checks for seeded scheduler jobs.
- Commands to run:
  - `uv run pytest tests/test_config.py tests/test_activity_service.py tests/test_ai_service.py tests/test_handlers.py tests/test_scheduler.py`
  - `uv run pytest`
