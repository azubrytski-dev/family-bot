ALTER TABLE weather_snapshots
    ADD COLUMN IF NOT EXISTS feels_like NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS wind_speed NUMERIC(5,2);

