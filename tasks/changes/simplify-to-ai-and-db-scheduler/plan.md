# Plan: simplify-to-ai-and-db-scheduler

## Steps

1. Freeze the target runtime surface in [app/main.py](/Users/andrei/projects/my_pets/family-bot/app/main.py) so startup wires only the AI stack, Telegram plumbing, PostgreSQL connection, and scheduler components needed for database-backed jobs.
2. Remove or disable non-goal modules from the active flow:
   - stop wiring legacy non-core modules and `InfoService`;
   - remove `/info` behavior and related feature flags from [app/core/config.py](/Users/andrei/projects/my_pets/family-bot/app/core/config.py);
   - keep code deletion scoped so AI chat and scheduler work do not regress.
3. Redefine scheduler architecture around database job definitions:
   - add scheduler-jobs storage to the active bootstrap schema;
   - add storage protocols and PostgreSQL repository methods for listing active jobs;
   - keep APScheduler as the executor, but make it load job definitions from storage instead of hardcoded cron entries in [app/bot/scheduler.py](/Users/andrei/projects/my_pets/family-bot/app/bot/scheduler.py).
4. Decide and document the minimum supported job model before implementation:
   - required fields such as job key, chat id, cron settings, enabled flag, and payload/template source;
   - how single-chat assumptions apply when `TARGET_CHAT_ID` and DB-defined chat ids differ;
   - what happens when the table is empty or contains invalid rows.
5. Simplify handler behavior in [app/bot/handlers.py](/Users/andrei/projects/my_pets/family-bot/app/bot/handlers.py) so inbound chat handling focuses on recording allowed chat context and forwarding AI-related behavior only.
6. Update configuration and startup safety:
   - remove stale env settings that only supported removed feature modules;
   - keep graceful degradation when scheduler jobs cannot be loaded;
   - keep the existing rule that at least one AI provider must be configured.
7. Add focused tests for the new boundaries:
   - config tests for the reduced feature set;
   - repository tests for scheduler job reads;
   - scheduler tests proving DB jobs are translated into APScheduler registrations;
   - handler/startup tests proving removed modules are no longer wired accidentally.
8. Run review gates before apply:
   - system design review for the new scheduler-job schema and chat-scope rules;
   - code review for boundary cleanup and async safety;
   - calamity review for empty-job tables, bad cron rows, and DB unavailability at startup.
