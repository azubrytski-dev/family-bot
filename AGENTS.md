# Codex Project Guide

This repository uses Codex as a disciplined implementation partner. The default expectation is:

1. Review the task and identify the affected layer.
2. Keep changes inside the smallest safe scope.
3. Run fast local verification before proposing an "apply" step.
4. Preserve architecture decisions unless the task explicitly reopens design.

## Product Context

- Product: family assistant Telegram bot for one configured family group chat.
- Runtime: Python 3.11+, `aiogram`, PostgreSQL, APScheduler, HTTP integrations.
- User-facing language: Russian.
- Internal code, comments, and technical docs: English.
- Reliability rule: graceful degradation is preferred over brittle "all or nothing" behavior.

## Architecture Boundaries

- `app/core/` owns business rules and service orchestration.
- `app/storage/` owns repository abstractions and PostgreSQL implementations.
- `app/integrations/` owns external API clients.
- `app/bot/` owns Telegram handlers, scheduling, and message formatting.
- Migrations are append-only. Avoid rewriting old migration files.

## Default Engineering Workflow

Follow this order unless the task clearly asks for something narrower:

`System Design Review -> Local Code -> Unit Tests -> Review -> Apply`

### Definition of "Apply Ready"

A change is ready to apply when all of the following are true:

- Scope is stated clearly, with explicit non-goals if needed.
- The architecture impact is understood.
- Unit tests cover the changed business logic.
- No new outbound bot behavior is introduced accidentally.
- Existing scheduler, repository, and config behavior remain coherent.

## Review Gates

### 1. System Design Review

Use before schema changes, new integrations, scheduling changes, or cross-layer refactors.

Check:

- data model implications;
- migration safety;
- scheduler and chat-scope impact;
- failure modes and fallback behavior;
- observability and operational risk.

### 2. Code Review

Check:

- readability and naming;
- boundary adherence;
- async correctness;
- security of config and network usage;
- regression risk in Telegram flows and storage logic.

### 3. Performance Review

Check:

- repeated DB queries or N+1 patterns;
- unnecessary API calls in scheduled jobs;
- blocking work in async paths;
- serialization/parsing overhead in hot paths.

### 4. Calamity / Stress Review

Check:

- startup with missing env vars;
- provider outages and fallback behavior;
- duplicate scheduler execution safety;
- DB connectivity failures;
- replay/idempotency for scheduled sends and persistence.

## Testing Rules

- Unit tests must be deterministic, isolated, and fast.
- Do not hit live Telegram, PostgreSQL, or third-party APIs in unit tests.
- Prefer fakes, stubs, and mocks around `app/integrations/` and storage boundaries.
- Add or update tests with behavior changes, not only implementation changes.

## Useful Local Commands

```bash
uv sync
uv run pytest
uv run python -m app.storage.migrate
uv run python -m app.main
```

If `uv` is unavailable, fall back to the existing virtualenv or `pip` workflow.
