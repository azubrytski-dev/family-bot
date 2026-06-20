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
    ('weather_morning', 'weather_morning', 7, 30, 'Europe/Minsk', NULL, TRUE),
    ('weather_alert_check', 'weather_alert_check', 7, 0, 'Europe/Minsk', NULL, FALSE)
ON CONFLICT (job_key) DO NOTHING;
