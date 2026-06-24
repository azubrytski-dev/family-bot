# Review Gate: family-session-memory-summary-feature

## Code Review

- Findings:
  - No blocking findings in step 1 after local verification.
  - Session storage stays inside `app/storage/`, orchestration stays in `app/core/services/`, and handler wiring only records approved-chat text messages plus the reply-to-bot flag.

## Performance Review

- Findings:
  - Session completion work currently runs opportunistically on message ingest, which keeps the first slice simple but may add extra DB work on busy chats.
  - Raw message deletion after archive limits long-term storage growth for completed sessions.

## Calamity Review

- Findings:
  - Invalid `TZ_NAME` falls back to `Europe/Minsk` instead of breaking message ingestion.
  - If LLM summary generation fails, the session archive does not run, so raw messages remain available for retry rather than being lost.

## Apply Recommendation

- Ready to apply: `step_1_only`
- Follow-ups:
  - Add scheduled consumption of archived summaries for morning messages.
  - Add evening-message generation from archived sessions.
  - Use archived session context in personal bot replies.
