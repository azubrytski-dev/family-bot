# Proposal: simplify-to-ai-and-db-scheduler

- Change ID: `simplify-to-ai-and-db-scheduler`
- Status: `proposed`
- Created: `2026-06-19`

## Objective

Reduce the active bot runtime to two product capabilities:

- AI-driven chat replies in the configured family chat;
- outbound scheduled messages defined by database rows instead of hardcoded cron entries.

## Scope

- In scope:
  - remove live startup wiring for legacy non-core feature modules;
  - remove stale config, docs, and live schema artifacts that no longer belong to the active product;
  - load scheduler jobs from PostgreSQL with a simplified fresh-start schema;
  - keep activity tracking because the night scheduler job still depends on it;
  - restore a narrow AI reply path for direct bot interactions in chat.
- Out of scope:
  - redesigning APScheduler itself;
  - expanding beyond the current single-family-chat assumptions.

## Design Review

- Affected layers: `app/main.py`, `app/bot/handlers.py`, `app/bot/scheduler.py`, `app/storage/repo.py`, `app/storage/pg_repo.py`, `app/storage/migrations/`.
- Data model / migration impact: fresh-start schema now contains only the active tables and seeds the existing morning and night jobs directly in `0001_init.sql`.
- Scheduler / outbound-message impact: scheduler callbacks remain the only scheduled outbound path, but their timing and target chat now come from DB rows with `TARGET_CHAT_ID` as fallback.
- Failure modes:
  - empty `scheduler_jobs` table leaves scheduler idle with a warning;
  - invalid or unsupported DB job rows are skipped instead of crashing startup;
  - AI replies still require at least one configured AI provider.

## Verification Plan

- Unit tests: scheduler loading, AI trigger detection, config behavior, activity service regression checks.
- Integration checks: full local `uv run pytest`.
- Review gates: code review, performance review, calamity review captured in `review.md`.
