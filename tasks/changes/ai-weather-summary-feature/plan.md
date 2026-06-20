# Plan: ai-weather-summary-feature

## Steps

1. Add append-only migration(s) for a generic config table and keep the schema minimal for weather-city configuration.
2. Extend the storage boundary with a config repository method that lists enabled values for a parameter such as `weather.city`.
3. Implement a small Open-Meteo client that resolves city names through geocoding and fetches current weather using async HTTP calls.
4. Add normalized weather models and a `WeatherService` that:
   - loads enabled cities from storage;
   - fetches weather per city;
   - builds a compact weather-specific prompt;
   - combines that prompt with the existing family-bot base prompt;
   - returns AI-generated Russian summary text with a deterministic fallback.
5. Extend handler wiring with `/weather_test` for approved chats, keeping behavior scoped to a manual test command only.
6. Wire the new repository and service in `app/main.py` without changing scheduler behavior.
7. Add focused deterministic tests for repository reads, service orchestration, and handler command mapping.
8. Run review gates and local verification before any apply-ready recommendation.
