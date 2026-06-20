CREATE TABLE IF NOT EXISTS app_config (
    id         BIGSERIAL   PRIMARY KEY,
    parameter  TEXT        NOT NULL,
    value      TEXT        NOT NULL,
    is_enabled BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS app_config_parameter_value_idx
    ON app_config (parameter, value);

CREATE INDEX IF NOT EXISTS app_config_parameter_idx
    ON app_config (parameter);
