# Review Gate: family-session-memory-summary-feature

## System Design Review

- Findings:
  - The design stays inside existing architecture boundaries: repositories own session persistence, the session-memory service owns summarization and context assembly, and bot/scheduler layers only orchestrate sending and triggering.
  - The schema change remains append-only through a new migration for expanding `chat_messages.message_text`, so existing deployments can migrate forward safely without rewriting history.
  - Session completion no longer depends only on message-driven expiry checks: an internal scheduler housekeeping job now finalizes expired sessions for low-traffic chats as well.

## Code Review

- Findings:
  - No blocking findings after local verification.
  - Session-aware personal replies stay inside the session-memory service and handler boundary: the handler only asks for reply context, while the service owns archived-summary lookup and current-session transcript assembly.
  - Deterministic tests now explicitly cover session completion, reply-to-bot handling, morning/evening prompt composition, successful raw-message cleanup, and raw-message retention on summary failure.

## Performance Review

- Findings:
  - Morning-message generation now performs one expired-session completion pass and one completed-summary lookup, which is a reasonable cost for a daily scheduled path.
  - Evening-message generation adds one extra open-session read and optional preview summary generation, which is acceptable for a once-per-day scheduled path.
  - Raw message deletion after archive limits long-term storage growth for completed sessions.
  - Personal replies now add one open-session read and up to two completed-session date lookups on AI-triggered messages, which is acceptable for the narrow mention/reply path and avoids any new global scheduler work.
  - The 15-minute housekeeping job adds a lightweight periodic expiry scan, which is a reasonable tradeoff for ensuring idle sessions are summarized without waiting for a new inbound message.

## Calamity Review

- Findings:
  - Invalid `TZ_NAME` falls back to `Europe/Minsk` instead of breaking message ingestion.
  - If LLM summary generation fails, the session archive does not run, so raw messages remain available for retry rather than being lost.
  - If the housekeeping pass fails on one run, sessions remain open with their raw messages intact and can be retried on the next message or the next interval pass.
  - If morning summary lookup or AI greeting generation fails, the scheduler now falls back to the existing static good-morning message instead of skipping the send.
  - If evening summary lookup, preview generation, or AI greeting generation fails, the scheduler now falls back to the existing static good-night message instead of skipping the send.
  - If session-memory context cannot be used for a personal reply, the handler still has the old direct-message context builder available as a fallback shape.

## Apply Recommendation

- Ready to apply: `full_change`
- Verification:
  - `uv run pytest` passed with `66 passed, 11 skipped`.
