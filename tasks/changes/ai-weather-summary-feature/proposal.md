# Proposal: ai-weather-summary-feature

- Change ID: `ai-weather-summary-feature`
- Status: `proposed`
- Created: `2026-06-20`

## Objective

Add a small weather flow for two DB-configured cities that fetches current weather from Open-Meteo and returns a short Russian AI summary with clothing advice.

## Scope

- In scope:
  - DB-backed config for enabled `weather.city` values;
  - Open-Meteo client for city lookup and current weather;
  - `WeatherService` to orchestrate fetch, prompt build, and AI output;
  - manual `/weather_test` command for approved chats;
  - deterministic tests for repo, service, and handler behavior.
- Out of scope:
  - scheduled weather delivery;
  - weather snapshot persistence;
  - multi-provider abstractions.

## Design Review

- Affected layers: storage migrations/repositories, weather integration, weather service, handlers, and startup wiring.
- Data model / migration impact:
  - add a generic config table with `parameter`, `value`, `is_enabled`, and timestamps;
  - add unique `(parameter, value)` and indexed `parameter`.
- Scheduler / outbound-message impact:
  - no scheduler changes;
  - outbound behavior is manual-only through `/weather_test`.
- Failure modes:
  - empty config returns a short Russian error;
  - one-city failure should still allow partial success;
  - total fetch failure returns a short fallback message;
  - AI failure falls back to deterministic non-AI text.

## Verification Plan

- Unit tests:
  - enabled config reads;
  - weather service success, partial failure, and AI fallback;
  - `/weather_test` gating and routing.
- Integration checks:
  - `uv run pytest`
- Review gates:
  - schema safety;
  - async HTTP and boundary adherence;
  - missing config and provider/AI outage handling.
