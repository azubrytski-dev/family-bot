# Plan: family-session-memory-summary-feature

## Steps

1. Session implementation, message storage, and session TTL:
   add `chat_messages` and `chat_sessions` storage, store only compact text messages, persist the mandatory `is_reply_to_bot` flag, keep sessions open for 6 hours, then complete the session by generating an LLM summary in Russian with participant names and key points, and delete session messages only after the summary is safely saved.
2. Morning daily message from yesterday sessions:
   update the scheduler and AI prompt flow so the morning message reads yesterday's completed session summaries and generates a short warm Russian greeting with encouragement or plan-aware context.
3. Evening message from yesterday plus today's sessions:
   update the evening scheduled flow so it uses yesterday's completed summaries together with today's completed sessions and generates a short Russian evening summary/good-night message in the same safe family tone.
4. Personal conversation with a user based on session context:
   update handler and AI reply orchestration so bot replies use session memory plus the mandatory reply-to-bot message flag, ensuring personal replies are grounded in the active conversational thread and the asking user's recent context.
5. Verification and review gates:
   add deterministic tests for session completion, deletion safety, reply-to-bot filtering, and morning/evening prompt composition, then run `uv run pytest` and complete system design, code, performance, and calamity review gates before marking the proposal apply-ready.
