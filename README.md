## Faminy Bot — Family Assistant Telegram Bot

A Telegram bot for a single family group chat that tracks daily activity, sends scheduled messages, provides weather/news/currency updates, and uses AI to answer mentions. All bot messages are in **Russian**.

### Features (MVP)

- **Single chat only**: ignores all chats except `TARGET_CHAT_ID`.
- **Daily activity tracking** per user with PostgreSQL storage.
- **Scheduled messages** in Minsk timezone (08:00 “доброе утро”, 23:00 “спокойной ночи”).
- **Weather snapshots** for configured cities with historical comparisons.
- **News aggregation** with AI-generated Russian summaries.
- **Currency rates** (EUR/USD/RUB → GEL, BYN) with history and deltas.
- **AI replies on mention** using Gemini with OpenAI fallback.

### Tech Stack

- Python 3.11+
- `aiogram` (Telegram bot)
- PostgreSQL
- Custom SQL migrations
- Gemini + OpenAI HTTP clients

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
- `TARGET_CHAT_ID` — numeric ID of the family chat. If omitted, the bot can participate in any chat, but scheduled messages are disabled.
- `WEATHER_CITIES` — comma-separated list of cities.
- `GEMINI_API_KEY`, `OPENAI_API_KEY` — AI providers.
- `POSTGRES_URL` — connection string to PostgreSQL.
- `TZ_NAME` — timezone, default `Europe/Minsk`.

3. **Run PostgreSQL locally**

You can use Docker, e.g.:

```bash
docker run --name faminy-bot-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=faminy_bot -p 5432:5432 -d postgres:16
```

4. **Run the bot**

```bash
python -m app.main
```

The bot will start polling Telegram and scheduling background jobs.

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

The initial test suite focuses on configuration loading and service skeletons; you can extend it with integration tests as the bot matures.

