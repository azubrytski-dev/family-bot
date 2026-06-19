# Task: Scheduler-only outbound messages

## Goal

Configure or evolve the bot so that **all outgoing Telegram messages** are sent **only** from **scheduled jobs** (APScheduler cron in `app/bot/scheduler.py`). The bot may still **receive** updates (polling) if needed for metrics, but it must **not** post replies or broadcasts from handlers, AI, or startup logic.

## In scope (must keep working)

- Scheduled sends as defined today (e.g. good morning ~08:00, good night ~23:00, and the nightly activity summary when activity tracking is part of that flow).
- `TARGET_CHAT_ID` and timezone behavior required for those jobs to target the right chat.
- Whatever persistence the scheduler jobs depend on (e.g. activity data for the summary) — still updated if the product still needs that summary.

## Out of scope / must not send (non-scheduler)

- Replies to `/start`, `/info`, `/activate` (either disable commands or make them no-op **without** calling `answer` / `reply`).
- Replies when the bot is **@mentioned** (no AI-driven `send_message` / `reply` from handlers).
- **Startup greeting** broadcast to chats on process start (not scheduler-driven).

## Acceptance criteria

1. Searching the runtime path for outbound sends: only scheduler callbacks (and shared helpers they call) may invoke `bot.send_message` / equivalent for user-visible text.
2. With normal use (users chatting and mentioning the bot), **no** new bot messages appear except at scheduled times.
3. Scheduled messages still fire at the configured times and content matches existing formatting rules.

## Notes

- Implementation approach (feature flags, handler stubs, or removing registrations) is left to the implementer; this file is **task definition only**.
- If activity summaries stay in the night job, inbound message handling may still need to **record** activity without **replying** — clarify in implementation.
