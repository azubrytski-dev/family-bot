## Faminy Bot — Family Assistant Telegram Bot

A Telegram bot for a single family group chat with a deliberately narrow active runtime: AI chat replies plus scheduled messages loaded from PostgreSQL. All bot messages are in **Russian**.

### Active Features

- **Single chat only**: ignores all chats except `TARGET_CHAT_ID`, unless a scheduler row provides its own `chat_id`.
- **Daily activity tracking** per user with PostgreSQL storage.
- **Database-backed scheduled messages** in Minsk timezone by default, seeded with 08:00 “доброе утро” and 23:00 “спокойной ночи” jobs.
- **AI replies on mention** using OpenAI.

### Tech Stack

- Python 3.11+
- `aiogram` (Telegram bot)
- PostgreSQL
- Custom SQL migrations
- OpenAI HTTP client

### Setup

1. **Clone & install dependencies**

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Using uv (optional)

If you use `uv`, the project already includes a `pyproject.toml`.

- **Create environment and install deps**:

```bash
uv sync
```

- **Run migrations**:

```bash
uv run app/storage/migrate.py
```

- **Run the bot**:

```bash
uv run app/main.py
```

2. **Configure environment**

- Copy `.env.example` to `.env` and fill values:

```bash
cp .env.example .env
```

Key variables:

- `BOT_TOKEN` — Telegram bot token.
- `TARGET_CHAT_ID` — numeric ID of the family chat. If omitted, DB scheduler rows must provide `chat_id` explicitly.
- `OPENAI_API_KEY` — OpenAI API key.
- `OPENAI_MODEL` — OpenAI model name, default `gpt-4.1-nano`.
- `POSTGRES_URL` — connection string to PostgreSQL.
- `TZ_NAME` — timezone, default `Europe/Minsk`.

3. **Run PostgreSQL locally**

You can use Docker, e.g.:

```bash
docker run --name faminy-bot-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=family_bot -p 5432:5432 -d postgres:16
```

4. **Run the bot**

```bash
python -m app.main
```

The bot will start polling Telegram and scheduling background jobs.

### Scheduler Jobs

Scheduler definitions live in the `scheduler_jobs` table. The fresh-start schema in `0001_init.sql` seeds two default jobs:

- `good_morning`
- `good_night_and_activity`

For now, job management is expected to happen directly in PostgreSQL.

> By default the bot will automatically apply any pending SQL migrations on startup (`AUTO_RUN_MIGRATIONS=true`).  
> If you prefer to manage them manually, set `AUTO_RUN_MIGRATIONS=false` and run:
>
> ```bash
> python -m app.storage.migrate
> ```

### Tests

Run tests with:

```bash
pytest
```

The test suite covers the active AI, scheduler, config, and storage paths; you can extend it with more integration coverage as the bot evolves.

### Migration Notes

The migration directory is intentionally simplified for fresh database bootstrap. `0001_init.sql` contains the complete active schema used by the bot today.
