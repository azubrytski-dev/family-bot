CREATE TABLE IF NOT EXISTS daily_activity (
    chat_id         BIGINT      NOT NULL,
    user_id         BIGINT      NOT NULL,
    activity_date   DATE        NOT NULL,
    message_count   INTEGER     NOT NULL DEFAULT 0,
    last_message_ts TIMESTAMPTZ,
    PRIMARY KEY (chat_id, user_id, activity_date)
);

CREATE TABLE IF NOT EXISTS chats (
    id               BIGSERIAL   PRIMARY KEY,
    chat_id          BIGINT      NOT NULL UNIQUE,
    title            TEXT,
    chat_type        TEXT        NOT NULL,
    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
    is_approved      BOOLEAN     NOT NULL DEFAULT FALSE,
    removed_at       TIMESTAMPTZ,
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_members_activity (
    chat_id           BIGINT      NOT NULL,
    user_id           BIGINT      NOT NULL,
    username          TEXT,
    display_name      TEXT,
    last_message_at   TIMESTAMPTZ,
    last_message_date DATE,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS scheduler_jobs (
    job_key       TEXT        PRIMARY KEY,
    job_type      TEXT        NOT NULL,
    cron_hour     SMALLINT    NOT NULL CHECK (cron_hour BETWEEN 0 AND 23),
    cron_minute   SMALLINT    NOT NULL CHECK (cron_minute BETWEEN 0 AND 59),
    timezone_name TEXT        NOT NULL DEFAULT 'Europe/Minsk',
    chat_id       BIGINT,
    enabled       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO scheduler_jobs (
    job_key,
    job_type,
    cron_hour,
    cron_minute,
    timezone_name,
    chat_id,
    enabled
)
VALUES
    ('good_morning', 'good_morning', 8, 0, 'Europe/Minsk', NULL, TRUE),
    ('good_night_and_activity', 'good_night_and_activity', 23, 0, 'Europe/Minsk', NULL, TRUE)
ON CONFLICT (job_key) DO NOTHING;
