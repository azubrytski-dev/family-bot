Technical Specification (Markdown)

# Family Assistant Telegram Bot

## Overview

Faminy Bot is a Telegram bot for a family chat with a deliberately narrow runtime:

- approval-based chat onboarding;
- daily activity tracking;
- database-backed scheduled messages;
- AI replies when the bot is explicitly addressed;
- a manual AI weather summary command for configured cities.

All user-facing bot messages are in **Russian**.

The implementation must favor **graceful degradation** over brittle all-or-nothing behavior.

---

# Product Scope

## Active Runtime Scope

The active product scope is:

- record chats that interact with the bot;
- only interact with chats approved in PostgreSQL;
- track daily per-user activity for approved chats;
- send scheduled morning and night messages from DB-defined scheduler jobs;
- answer explicit bot-directed chat messages through OpenAI;
- generate a short weather summary for DB-configured cities through a manual test command.

## Out of Scope

The following are not part of the active scope unless reopened explicitly:

- news aggregation;
- currency rates;
- multi-provider weather architecture;
- weather snapshot persistence;
- broad configuration UI inside Telegram.

---

# Core Features

## 1. Approval-Based Chat Operation

The bot may observe incoming updates from multiple chats, but it must only interact with chats that are approved in the database.

### Behavior

- every incoming message or membership update may register a chat as seen;
- unapproved chats are recorded but do not receive normal bot interactions;
- removed chats are marked inactive and require approval again if the bot is added back;
- test commands are additionally gated by a per-chat `allow_test` flag.

### Data stored

- chat id;
- title;
- chat type;
- active/inactive state;
- approval flag;
- test-command flag;
- removal timestamp;
- last seen timestamp.

---

## 2. Daily Activity Tracking

The bot tracks whether each known member of an approved chat has written at least one message on a given day.

### Behavior

- inbound messages update both last-seen activity and daily counters;
- the night scheduler flow uses this data to produce an activity summary;
- if everyone has written, the summary is positive;
- if someone was inactive, the summary names those users.

### Data stored

- `chat_id`
- `user_id`
- `activity_date`
- `message_count`
- `last_message_ts`

Additional member labels are stored separately for human-friendly summaries.

---

## 3. Scheduled Messages

Scheduled messages are loaded from PostgreSQL and executed by APScheduler.

### Current supported job types

| Job type | Default schedule | Behavior |
|------|------|------|
| `good_morning` | 08:00 Europe/Minsk | sends a short morning greeting |
| `good_night_and_activity` | 23:00 Europe/Minsk | sends a good-night message, then a daily activity summary |

### Behavior

- scheduler definitions live in the `scheduler_jobs` table;
- only enabled rows are registered at startup;
- unsupported job types are skipped with logging;
- rows without `chat_id` are skipped with logging;
- scheduler startup failure should be visible in logs and should not silently invent fallback jobs.

### Design constraint

Scheduled behavior must remain coherent with activity tracking and approved-chat expectations.

---

## 4. AI Chat Replies

The bot uses OpenAI for short conversational replies in Russian.

### Trigger rules

- the bot replies only when explicitly mentioned by username;
- or when a message replies directly to a previous bot message.

### Prompting

- reuse the existing family-bot base prompt;
- keep replies friendly, concise, and practical;
- avoid pretending to know missing context.

---

## 5. AI Weather Summary

Add a small weather feature for DB-configured cities.

### Goal

Generate a compact Russian weather summary that:

- mentions the configured cities;
- summarizes the current weather simply;
- adds a practical clothing suggestion;
- avoids technical overload or invented facts.

### Runtime flow

`config -> weather API fetch -> normalized payload -> AI prompt build -> Russian summary -> Telegram message`

### Command entrypoint

Manual test command:

- `/weather_test`

### Behavior

The command must:

1. load enabled weather cities from the database;
2. fetch weather for each configured city from Open-Meteo;
3. normalize the external response into an internal weather object;
4. build a weather-specific prompt on top of the existing family-bot base prompt;
5. ask the AI service for the final Russian message;
6. send the final summary back to the approved chat.

### Output expectations

The weather response should be:

- short;
- family-friendly;
- practical;
- limited to 1 to 2 concise sentences when possible.

The weather response should not:

- dump raw JSON;
- overexplain meteorological details;
- invent weather facts not present in the payload;
- make medical or dangerous recommendations.

### Failure handling

- if no enabled weather cities exist, return a short Russian configuration message;
- if one city fails to resolve or fetch, prefer partial success if another city succeeds;
- if all city fetches fail, return a short Russian fallback message;
- if AI generation fails, fall back to a deterministic non-AI summary built from normalized weather data.

---

# Integrations

## OpenAI

Used for:

- conversational replies;
- weather-summary text generation.

## Open-Meteo

Used for:

- city geocoding by name;
- current weather fetch by coordinates.

### Integration rule

Do not overdesign provider abstractions for the first version. One weather provider is enough.

---

# Data Model

Database: PostgreSQL

Schema is managed by append-only migrations.

## Active Tables

### `chats`

- `chat_id`
- `title`
- `chat_type`
- `is_active`
- `is_approved`
- `allow_test`
- `removed_at`
- `last_seen_at`

### `chat_members_activity`

- `chat_id`
- `user_id`
- `username`
- `display_name`
- `last_message_at`
- `last_message_date`
- `updated_at`

### `daily_activity`

- `chat_id`
- `user_id`
- `activity_date`
- `message_count`
- `last_message_ts`

### `scheduler_jobs`

- `job_key`
- `job_type`
- `cron_hour`
- `cron_minute`
- `timezone_name`
- `chat_id`
- `enabled`
- timestamps

### `app_config`

Purpose: generic DB-backed runtime configuration.

Fields:

- `id`
- `parameter`
- `value`
- `is_enabled`
- `created_at`
- `updated_at`

Constraints:

- unique index on `(parameter, value)`
- index on `parameter`

Initial weather usage:

- `parameter = 'weather.city'`
- `value = 'Minsk'`
- `is_enabled = true`

---

# Architecture

## Layer Responsibilities

### `app/bot/`

Owns:

- Telegram handlers;
- scheduler registration and callbacks;
- user-facing formatting.

### `app/core/`

Owns:

- business models;
- orchestration services;
- prompt composition rules.

### `app/storage/`

Owns:

- repository abstractions;
- PostgreSQL implementations;
- SQL migrations.

### `app/integrations/`

Owns:

- external HTTP clients for OpenAI and weather APIs.

## Weather Modules

### `app/integrations/weather/client.py`

Responsibilities:

- resolve city names through Open-Meteo geocoding;
- fetch current weather by coordinates;
- return normalized Python structures or DTO-ready data for the service layer.

### `app/core/services/weather_service.py`

Responsibilities:

- load enabled `weather.city` values from storage;
- orchestrate weather fetches for configured cities;
- normalize and assemble structured weather payloads;
- build weather-specific prompt input;
- call the AI service;
- produce a deterministic fallback summary when AI is unavailable.

### Storage extension

Repository layer should expose a narrow method for reading enabled config values by parameter.

---

# Configuration

## Environment

Required:

- `BOT_TOKEN`
- `OPENAI_API_KEY`
- `POSTGRES_URL`

Optional:

- `OPENAI_MODEL` default `gpt-4.1-nano`
- `TZ_NAME` default `Europe/Minsk`
- `ENABLE_SCHEDULER`
- `ENABLE_ACTIVITY_TRACKING`
- `AUTO_RUN_MIGRATIONS`

## Database-Backed Config

Weather cities must come from PostgreSQL, not from environment variables or hardcoded lists.

First supported config key:

- `weather.city`

---

# Reliability Requirements

## Graceful Degradation

- external weather provider failures must not crash the bot process;
- partial weather success is better than total failure;
- AI failures should degrade to deterministic text when feasible;
- invalid or unsupported scheduler rows should be skipped, not crash startup;
- missing config should produce explicit short operator-visible behavior.

## Observability

Log at least:

- skipped scheduler rows;
- weather geocoding/fetch failures;
- AI generation failures when fallback is used;
- empty weather-city configuration for `/weather_test`.

---

# Testing Requirements

- unit tests must be deterministic, isolated, and fast;
- tests must not hit live Telegram, PostgreSQL, OpenAI, or Open-Meteo;
- use fakes, mocks, or stubs around repository and integration boundaries;
- add tests for behavior changes, not just implementation details.

## Minimum weather test coverage

- config repository returns enabled city values;
- weather service handles two-city success;
- weather service handles one-city failure with partial success;
- weather service falls back when AI generation fails;
- handler command wiring respects approval and test-command gating.

---

# MVP Scope

Current MVP includes:

- approval-based chat onboarding;
- PostgreSQL-backed persistence;
- morning and night scheduled messages;
- daily activity tracking;
- AI replies on mention;
- manual AI weather summary command for DB-configured cities.

---

# Future Enhancements

Possible future features:

- scheduled weather delivery;
- admin flows for managing `app_config` entries;
- weather snapshot persistence;
- reminders;
- birthdays;
- family calendar.
