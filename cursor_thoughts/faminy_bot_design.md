## Family Assistant Telegram Bot — Design

This document summarizes the initial architecture and implementation plan for the family assistant Telegram bot.

---

## Folder Structure

```text
.
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py
│   │   ├── scheduler.py
│   │   └── formatting.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── models.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── activity_service.py
│   │       ├── weather_service.py
│   │       ├── news_service.py
│   │       ├── currency_service.py
│   │       └── ai_service.py
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── telegram/
│   │   │   └── __init__.py
│   │   ├── weather/
│   │   │   ├── __init__.py
│   │   │   └── client.py
│   │   ├── news/
│   │   │   ├── __init__.py
│   │   │   └── client.py
│   │   ├── rates/
│   │   │   ├── __init__.py
│   │   │   └── client.py
│   │   └── ai/
│   │       ├── __init__.py
│   │       ├── gemini_client.py
│   │       └── openai_client.py
│   └── storage/
│       ├── __init__.py
│       ├── repo.py
│       ├── pg_repo.py
│       ├── migrate.py
│       └── migrations/
│           ├── __init__.py
│           ├── 0001_init.sql
│           └── 0002_seed_news_sources.sql
├── tasks/
│   ├── tech-spec.md
│   └── initial.md
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   └── test_activity_service.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## PostgreSQL Schema

```sql
CREATE TABLE chat_members (
    chat_id        BIGINT      NOT NULL,
    user_id        BIGINT      NOT NULL,
    username       TEXT,
    display_name   TEXT,
    is_active      BOOLEAN     NOT NULL DEFAULT TRUE,
    joined_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE daily_activity (
    chat_id         BIGINT      NOT NULL,
    user_id         BIGINT      NOT NULL,
    activity_date   DATE        NOT NULL,
    message_count   INTEGER     NOT NULL DEFAULT 0,
    last_message_ts TIMESTAMPTZ,
    PRIMARY KEY (chat_id, user_id, activity_date)
);

CREATE TABLE weather_snapshots (
    id          BIGSERIAL   PRIMARY KEY,
    city        TEXT        NOT NULL,
    snapshot_date DATE      NOT NULL,
    temperature NUMERIC(5,2),
    condition   TEXT,
    raw_payload JSONB,
    UNIQUE (city, snapshot_date)
);

CREATE TABLE currency_rates (
    id              BIGSERIAL   PRIMARY KEY,
    base_currency   CHAR(3)     NOT NULL,
    target_currency CHAR(3)     NOT NULL,
    rate_date       DATE        NOT NULL,
    rate            NUMERIC(12,6) NOT NULL,
    UNIQUE (base_currency, target_currency, rate_date)
);

CREATE TABLE news_sources (
    id        SERIAL      PRIMARY KEY,
    name      TEXT        NOT NULL,
    country   TEXT        NOT NULL,
    category  TEXT        NOT NULL, -- 'Georgia' | 'Belarus' | 'World'
    url       TEXT        NOT NULL,
    enabled   BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE TABLE news_items (
    id            BIGSERIAL   PRIMARY KEY,
    source_id     INTEGER     NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
    title         TEXT        NOT NULL,
    url           TEXT        NOT NULL,
    published_at  TIMESTAMPTZ NOT NULL,
    content_hash  TEXT        NOT NULL,
    raw_payload   JSONB,
    UNIQUE (source_id, content_hash)
);

CREATE TABLE schema_migrations (
    version     TEXT        PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Migration Strategy

- **Format**: numbered `.sql` files in `app/storage/migrations`, e.g. `0001_init.sql`, `0002_seed_news_sources.sql`.
- **Tracking**: `schema_migrations` table stores applied migration `version` (file name) and timestamp.
- **Runner**: `app/storage/migrate.py`:
  - Connects to PostgreSQL using `POSTGRES_URL`.
  - Ensures `schema_migrations` exists.
  - Lists all `.sql` files in `migrations/`, sorts by filename.
  - Applies only those files not present in `schema_migrations`, in order, inside a transaction per file.
- **News sources seeding**: `0002_seed_news_sources.sql` inserts default feeds for Georgia, Belarus, and World categories, which can later be changed by editing or adding migrations.

Example seed migration:

```sql
INSERT INTO news_sources (name, country, category, url, enabled) VALUES
  ('agenda.ge', 'Georgia', 'Georgia', 'https://agenda.ge', TRUE),
  ('civil.ge',  'Georgia', 'Georgia', 'https://civil.ge', TRUE),
  ('onliner.by','Belarus', 'Belarus', 'https://www.onliner.by', TRUE),
  ('zerkalo.io','Belarus', 'Belarus', 'https://news.zerkalo.io', TRUE),
  ('BBC',       'UK',      'World',   'https://www.bbc.com', TRUE),
  ('Reuters',   'Global',  'World',   'https://www.reuters.com', TRUE);
```

---

## Config Model

`app/core/config.py` will expose a single `AppConfig` object backed by environment variables.

Key fields:

- `bot_token: str`
- `target_chat_id: int`
- `weather_cities: list[str]`
- `gemini_api_key: str | None`
- `openai_api_key: str | None`
- `postgres_url: str`
- `tz_name: str` (default: `Europe/Minsk`)

The config will be implemented with `pydantic.BaseSettings`, loading values from both environment and a local `.env` file during development.

Example `.env.example`:

```env
BOT_TOKEN=your-telegram-bot-token
TARGET_CHAT_ID=123456789

WEATHER_CITIES=Minsk,Tbilisi,Batumi

GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key

POSTGRES_URL=postgresql://user:password@localhost:5432/faminy_bot
```

---

## Code Skeleton — Main Modules

### `app/main.py`

- Initialize logging.
- Load `AppConfig`.
- Initialize DB connection and repositories.
- Initialize AI clients (Gemini primary, OpenAI fallback).
- Initialize services (activity, weather, news, currency, AI).
- Wire services into bot handlers and scheduler.
- Start Telegram polling (or webhook later) and APScheduler with Minsk timezone.

### `app/bot/handlers.py`

- Define message handlers using `aiogram`:
  - Ignore all messages not from `TARGET_CHAT_ID`.
  - For regular messages in target chat:
    - Update daily activity via `ActivityService`.
  - When the bot is mentioned:
    - Build a Russian-language prompt and call `AiService` to generate a reply.
    - Send reply back to the same message thread.

### `app/bot/scheduler.py`

- Configure scheduled jobs (Minsk time, using APScheduler):
  - 08:00 — send "Доброе утро" message, plus optional weather/currency snapshot.
  - 23:00 — send "Спокойной ночи" message and daily activity summary.
  - Periodic jobs for:
    - Weather snapshots (e.g. hourly or daily).
    - News fetch + AI summaries.
    - Currency rates snapshots.

### `app/core/services/*`

- `ActivityService`
  - Record user messages per day.
  - Compute who has/has not written today.
  - Provide daily summary for scheduler.
- `WeatherService`
  - Fetch and store daily weather snapshots.
  - Provide comparisons: today vs yesterday vs 7 days ago.
- `NewsService`
  - Fetch raw news items from DB-configured sources.
  - Store items; deduplicate by `content_hash`.
  - Ask `AiService` for Russian summaries per category.
- `CurrencyService`
  - Fetch and persist daily FX rates.
  - Provide deltas vs yesterday and 7 days ago.
- `AiService`
  - High-level API for:
    - `summarize_news(items, category) -> str`
    - `reply_to_mention(context) -> str`
    - `optional_commentary(context) -> str | None`
  - Uses Gemini as primary provider, falls back to OpenAI on error or unavailability.

### `app/integrations/*`

- `weather.client`: wraps chosen weather API provider.
- `news.client`: wraps one or more RSS/HTTP news feeds.
- `rates.client`: wraps exchange-rate API or central bank endpoints.
- `ai.gemini_client` / `ai.openai_client`: thin HTTP clients for respective AI APIs.

### `app/storage/*`

- `repo.py`
  - Repository protocol interfaces, e.g. `ActivityRepository`, `WeatherRepository`, `NewsRepository`, `CurrencyRepository`, `ChatMembersRepository`.
- `pg_repo.py`
  - PostgreSQL implementations of the repository interfaces, using async DB driver.
- `migrate.py`
  - Simple CLI/entrypoint to run SQL migrations from `migrations/`.

---

## Phased Implementation Plan

### Phase 1 — Skeleton & Infrastructure

- Create project structure, config model, and `requirements.txt`.
- Implement migration runner and initial schema migrations.
- Add basic logging and app bootstrap in `main.py`.

### Phase 2 — Telegram & Activity Tracking (MVP Core)

- Integrate `aiogram` bot with `BOT_TOKEN`.
- Restrict bot to `TARGET_CHAT_ID`.
- Implement `ActivityService` and repository.
- Track daily messages and implement checks for inactive users vs everyone active.
- Add morning and night scheduled messages (no external data yet).

### Phase 3 — Weather, Currency, News (Data Integrations)

- Implement weather API client and `WeatherService`.
- Implement FX rates client and `CurrencyService`.
- Implement news fetching client and `NewsService`, using DB-configured sources.
- Store snapshots and historical data; expose comparison helpers for bot messages.

### Phase 4 — AI Integration

- Implement `GeminiClient` and `OpenAIClient`.
- Implement `AiService` with provider fallback.
- Use AI for:
  - Summarizing daily/periodic news digests in Russian.
  - Answering mentions in chat with Russian replies.
  - Optional commentary for weather/currency/activity summaries.

### Phase 5 — Testing & Hardening

- Add unit tests for config, services, and repository logic (with mocked DB/clients).
- Add integration tests for migration runner against a local PostgreSQL instance.
- Improve error handling, logging, and idempotency for scheduled jobs.

