CREATE TABLE IF NOT EXISTS chat_sessions (
    id               BIGSERIAL   PRIMARY KEY,
    chat_id          BIGINT      NOT NULL,
    local_date       DATE        NOT NULL,
    started_at_utc   TIMESTAMPTZ NOT NULL,
    expires_at_utc   TIMESTAMPTZ NOT NULL,
    completed_at_utc TIMESTAMPTZ,
    status           TEXT        NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'completed')),
    message_count    INTEGER     NOT NULL DEFAULT 0 CHECK (message_count >= 0),
    summary_text     TEXT        CHECK (summary_text IS NULL OR char_length(summary_text) <= 500),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS chat_sessions_one_open_per_chat
    ON chat_sessions (chat_id)
    WHERE status = 'open';

CREATE INDEX IF NOT EXISTS chat_sessions_completed_lookup_idx
    ON chat_sessions (chat_id, local_date, completed_at_utc DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id                  BIGSERIAL   PRIMARY KEY,
    chat_id             BIGINT      NOT NULL,
    session_id          BIGINT      NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    telegram_message_id BIGINT      NOT NULL,
    user_id             BIGINT      NOT NULL,
    username            TEXT,
    display_name        TEXT,
    message_text        TEXT        NOT NULL CHECK (char_length(message_text) <= 100),
    message_ts_utc      TIMESTAMPTZ NOT NULL,
    local_date          DATE        NOT NULL,
    is_reply_to_bot     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (chat_id, telegram_message_id)
);

CREATE INDEX IF NOT EXISTS chat_messages_session_lookup_idx
    ON chat_messages (session_id, message_ts_utc, id);

CREATE INDEX IF NOT EXISTS chat_messages_chat_lookup_idx
    ON chat_messages (chat_id, local_date, message_ts_utc);
