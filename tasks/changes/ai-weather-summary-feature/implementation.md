# Implementation: ai-weather-summary-feature

## Working Notes

- Target files:
  - `app/storage/migrations/0005_add_app_config.sql`
  - `app/storage/repo.py`
  - `app/storage/pg_repo.py`
  - `app/core/models.py`
  - `app/core/services/ai_service.py`
  - `app/core/services/weather_service.py`
  - `app/integrations/weather/client.py`
  - `app/bot/handlers.py`
  - `app/main.py`
- Key assumptions:
  - weather cities are operator-managed through `app_config` rows with `parameter = 'weather.city'`;
  - Open-Meteo geocoding plus current-weather fetch is sufficient for the first iteration;
  - `/weather_test` should follow the existing approved-chat and `allow_test` gating rules.
- Risks to watch:
  - city-name ambiguity from geocoding may resolve to an unexpected location if operators use vague names;
  - the deterministic fallback is intentionally simple and may read less naturally than the AI output;
  - the feature currently depends on live Open-Meteo availability at command time because snapshots are out of scope.

## Test Plan

- Unit tests to add/update:
  - AI prompt coverage for weather summary generation;
  - handler command parsing for `/weather_test`;
  - repository read path for enabled `app_config` values;
  - weather service success, partial failure, missing config, and AI fallback behavior;
  - runtime resource cleanup for the weather client.
- Commands to run:
  - `uv run pytest tests/test_ai_service.py tests/test_handlers.py tests/test_main.py tests/test_repositories.py tests/test_scheduler.py tests/test_weather_service.py`
  - `uv run pytest`
