CREATE TABLE IF NOT EXISTS chats (
    id               BIGSERIAL   PRIMARY KEY,
    chat_id          BIGINT      NOT NULL UNIQUE,
    title            TEXT,
    chat_type        TEXT        NOT NULL,
    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_greeting_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chat_members_activity (
    chat_id          BIGINT      NOT NULL,
    user_id          BIGINT      NOT NULL,
    username         TEXT,
    display_name     TEXT,
    last_message_at  TIMESTAMPTZ,
    last_message_date DATE,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

