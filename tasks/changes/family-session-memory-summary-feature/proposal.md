# Proposal: family-session-memory-summary-feature

- Change ID: `family-session-memory-summary-feature`
- Status: `proposed`
- Created: `2026-06-22`

## Objective

Add a compact family-memory layer that stores short recent text messages, groups them into time-bounded sessions, summarizes completed sessions with the LLM in Russian, and reuses those summaries for family greetings plus bot replies in personal conversations.

## Scope

- In scope:
  - append-only PostgreSQL tables for compact message memory and per-chat sessions;
  - repository interfaces and PostgreSQL implementations for writing recent messages, marking whether a message is a reply to the bot, reading open/completed session context, and persisting completed session summaries;
  - a core memory/session service that trims stored text, computes `local_date` from `TZ_NAME`, closes a session after 6 hours, asks the LLM to summarize it with participant names plus key points, and deletes raw message rows once the session is completed;
  - `AiService` prompt assembly changes so personal replies, morning messages, evening messages, and summary generation share one Russian-language prompt policy and the event-aware safety rules from the original brief;
  - handler and scheduler wiring needed to record approved-chat text messages, preserve the reply-to-bot signal for personal conversations, and consume stored summaries for morning/evening messages;
  - deterministic unit tests for storage-free business logic, AI prompt assembly, and scheduler/handler orchestration.
- Out of scope:
  - long-term raw transcript storage beyond the compact recent-message window;
  - support for non-text media summarization;
  - semantic search, embeddings, or vector storage;
  - a broad memory redesign for unrelated bot features;
  - changing existing weather behavior except where the shared Russian prompt chain is reused;
  - rewriting previous migrations.

## Functional Details

- Message storage examples:
  - store only text messages;
  - trim `message_text` to 100 chars max;
  - ignore empty and non-text content for now;
  - store UTC timestamp plus derived `local_date`;
  - persist a mandatory boolean flag such as `is_reply_to_bot` so personal bot conversations can be reconstructed safely.
- Session lifecycle:
  - an open session collects recent compact messages for the chat;
  - after 6 hours, the session is considered complete;
  - completion triggers LLM summarization in Russian with participant names and a few useful key points;
  - once the summary is saved, raw messages from that session are deleted so the bot does not keep full history forever.
- Summary expectations:
  - short, neutral, family-friendly, and max 500 chars;
  - include who was active, what topics or plans came up, and the emotional tone only when obvious and safe;
  - avoid transcript-style retelling, direct quotes, and highly sensitive details.
- Prompt behavior examples:
  - if someone is sick, answers can gently wish recovery;
  - if someone mentions an exam, trip, or interview, answers can wish calm and good luck;
  - if something negative happened, the bot should not repeat painful details and should stay warm but neutral with phrasing like `пусть сегодняшний день будет чуть легче и спокойнее`.
- Morning message context:
  - use yesterday's completed session summaries;
  - optionally include a recent broader summary if it helps;
  - generate a short warm greeting that reflects plans, encouragement, or ongoing family context.
- Evening message context:
  - use yesterday's completed summaries plus today's completed sessions;
  - generate a short family-aware evening wrap-up in Russian with a calm, safe tone.
- Personal conversation context:
  - when the bot is mentioned or a user replies to the bot, include the asking user's identity, recent completed session summaries, and messages marked `is_reply_to_bot = true` from the active conversational thread;
  - this keeps personal replies grounded in the actual ongoing exchange, not just generic family memory.

## Design Review

- Affected layers: `app/storage/` migrations and repositories, a new memory-oriented service in `app/core/services/`, `app/core/models.py`, `app/bot/handlers.py`, `app/bot/scheduler.py`, `app/main.py`, and `app/integrations/ai/openai_client.py` only if summary-generation call shapes need extension.
- Data model / migration impact:
  - add append-only tables for compact `chat_messages` and `chat_sessions`;
  - `chat_messages` should include identifiers such as `chat_id`, `session_id`, `telegram_message_id`, `user_id`, `username`, `display_name`, `message_text`, `message_ts_utc`, `local_date`, `is_reply_to_bot`, and `created_at`;
  - `chat_sessions` should include `chat_id`, session timing, lifecycle status, `message_count`, and `summary_text`;
  - persist UTC timestamps plus derived `local_date` so date grouping stays stable under configured timezone changes;
  - session completion should be explicit so message deletion happens only after summary persistence succeeds.
- Scheduler / outbound-message impact:
  - morning and evening jobs will become AI-backed and summary-aware instead of purely static formatting;
  - morning output should use yesterday summaries;
  - evening output should use yesterday plus today's completed sessions;
  - session completion and summarization must remain safe if a scheduled run overlaps with message-triggered updates;
  - outbound copy must stay Russian and should avoid accidental behavior changes for unrelated scheduler jobs.
- Failure modes:
  - if summary generation fails, retain the raw session messages and retry later rather than deleting context prematurely;
  - if no recent context exists, AI replies should still answer naturally with the base family prompt;
  - duplicate or overlapping completion runs must not create multiple summaries or delete messages twice;
  - if only partial user metadata is present, the summary should still use the best available name label;
  - missing or invalid `TZ_NAME` should degrade to the configured default behavior rather than breaking message handling.

## Verification Plan

- Unit tests:
  - message-context trimming, local-date derivation, 6-hour session completion, and message deletion gating after successful summary persistence;
  - repository-facing service behavior for open/completed session selection, reply-to-bot filtering, and fallback handling;
  - `AiService` prompt composition for personal replies and scheduled-message generation using completed session summaries;
  - handler/scheduler tests proving approved-chat gating and no accidental outbound behavior for unrelated paths.
- Integration checks:
  - `uv run pytest`
- Review gates:
  - system design review for migration safety, session TTL behavior, deletion safety, and scheduler overlap behavior;
  - code review for async boundary adherence and prompt-safety handling around negative events;
  - performance/calamity review for storage growth, repeated summary work, DB outages, and AI-provider failures.
