# Review Gate: family-session-memory-summary-feature

## Code Review

- Findings:
  - No blocking findings in step 4 after local verification.
  - Session-aware personal replies stay inside the session-memory service and handler boundary: the handler only asks for reply context, while the service owns archived-summary lookup and current-session transcript assembly.

## Performance Review

- Findings:
  - Morning-message generation now performs one expired-session completion pass and one completed-summary lookup, which is a reasonable cost for a daily scheduled path.
  - Evening-message generation adds one extra open-session read and optional preview summary generation, which is acceptable for a once-per-day scheduled path.
  - Raw message deletion after archive limits long-term storage growth for completed sessions.
  - Personal replies now add one open-session read and up to two completed-session date lookups on AI-triggered messages, which is acceptable for the narrow mention/reply path and avoids any new global scheduler work.

## Calamity Review

- Findings:
  - Invalid `TZ_NAME` falls back to `Europe/Minsk` instead of breaking message ingestion.
  - If LLM summary generation fails, the session archive does not run, so raw messages remain available for retry rather than being lost.
  - If morning summary lookup or AI greeting generation fails, the scheduler now falls back to the existing static good-morning message instead of skipping the send.
  - If evening summary lookup, preview generation, or AI greeting generation fails, the scheduler now falls back to the existing static good-night message instead of skipping the send.
  - If session-memory context cannot be used for a personal reply, the handler still has the old direct-message context builder available as a fallback shape.

## Apply Recommendation

- Ready to apply: `step_4_only`
- Follow-ups:
  - Consider a background session-expiration job for completely idle chats so summary creation does not depend on the next inbound message.
