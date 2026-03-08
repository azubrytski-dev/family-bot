## Init phase summary

- **Database**: Added `chats` and `chat_members_activity` tables and wired new PostgreSQL repositories for chat registry and lightweight last-activity tracking.
- **Services**: Introduced `ChatRegistryService`, `InfoService`, and extended `AiService` with a shared Zubrytski family base prompt used for conversational AI replies.
- **Bot wiring**: Updated `main` and `handlers` to use the new services, support optional `TARGET_CHAT_ID`, track known chats, send startup greetings, reply on mention with AI, and implement `/info` with weather and currency summary.
- **Tests**: Added tests for the AI persona prompt usage and the `/info` summary composition.

