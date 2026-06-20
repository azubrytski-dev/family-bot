# Review Gate: simplify-to-ai-and-db-scheduler

## Code Review

- Findings:
  - Startup wiring now keeps the active surface smaller by removing legacy non-core initialization from `app/main.py`.
  - Scheduler configuration is now storage-backed with a dedicated repository boundary instead of hardcoded cron definitions only.
  - AI reply behavior is intentionally narrow and tied to explicit bot-directed messages.
  - Unused legacy feature modules and tests were removed to align the codebase with the active product.
  - The migration set is simplified for fresh bootstrap, so new databases only create the active schema.

## Performance Review

- Findings:
  - Scheduler job loading is one DB read at startup and does not add per-message database work.
  - Inbound message cost remains bounded to chat registration, optional activity tracking, and AI generation only for direct bot-trigger messages.

## Calamity Review

- Findings:
  - Empty scheduler tables degrade safely by leaving the scheduler idle with a warning.
  - Missing DB chat ids on scheduler rows fall back to `TARGET_CHAT_ID`; if neither is present, the row is skipped.
  - AI provider absence still fails fast at startup, which is appropriate for an AI-first runtime.

## Apply Recommendation

- Ready to apply: yes
- Follow-ups:
  - consider validating timezone names and cron ranges more aggressively at write time for `scheduler_jobs`;
  - if shared environments still carry old schema state, recreate them from scratch before relying on the new migration layout.
