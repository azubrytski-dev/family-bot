CREATE TABLE IF NOT EXISTS chat_members (
    chat_id        BIGINT      NOT NULL,
    user_id        BIGINT      NOT NULL,
    username       TEXT,
    display_name   TEXT,
    is_active      BOOLEAN     NOT NULL DEFAULT TRUE,
    joined_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS daily_activity (
    chat_id         BIGINT      NOT NULL,
    user_id         BIGINT      NOT NULL,
    activity_date   DATE        NOT NULL,
    message_count   INTEGER     NOT NULL DEFAULT 0,
    last_message_ts TIMESTAMPTZ,
    PRIMARY KEY (chat_id, user_id, activity_date)
);

CREATE TABLE IF NOT EXISTS weather_snapshots (
    id            BIGSERIAL   PRIMARY KEY,
    city          TEXT        NOT NULL,
    snapshot_date DATE        NOT NULL,
    temperature   NUMERIC(5,2),
    condition     TEXT,
    raw_payload   JSONB,
    UNIQUE (city, snapshot_date)
);

CREATE TABLE IF NOT EXISTS currency_rates (
    id              BIGSERIAL     PRIMARY KEY,
    base_currency   CHAR(3)       NOT NULL,
    target_currency CHAR(3)       NOT NULL,
    rate_date       DATE          NOT NULL,
    rate            NUMERIC(12,6) NOT NULL,
    UNIQUE (base_currency, target_currency, rate_date)
);

CREATE TABLE IF NOT EXISTS news_sources (
    id       SERIAL      PRIMARY KEY,
    name     TEXT        NOT NULL,
    country  TEXT        NOT NULL,
    category TEXT        NOT NULL,
    url      TEXT        NOT NULL,
    enabled  BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS news_items (
    id            BIGSERIAL   PRIMARY KEY,
    source_id     INTEGER     NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
    title         TEXT        NOT NULL,
    url           TEXT        NOT NULL,
    published_at  TIMESTAMPTZ NOT NULL,
    content_hash  TEXT        NOT NULL,
    raw_payload   JSONB,
    UNIQUE (source_id, content_hash)
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

