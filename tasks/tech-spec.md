Technical Specification (Markdown)

# Family Assistant Telegram Bot

## Overview

A Telegram bot designed to work with **one specific family group chat**.

The bot monitors chat activity, sends scheduled messages, and uses AI to interact with users.

All bot communication is in **Russian**.

---

# Core Features

## 1. Single Chat Operation

The bot must only work with one configured chat.

Config variable:

TARGET_CHAT_ID

If a message comes from another chat, it must be ignored.

---

# 2. Daily Activity Tracking

The bot tracks whether each chat member writes at least one message per day.

### Behavior

If someone has not written today:
- bot notifies the chat and mentions inactive users.

If everyone has written:
- bot posts a positive message.

### Data stored

Daily message metrics per user.

---

# 3. Scheduled Messages

Using Minsk timezone.

| Event | Time |
|------|------|
Good morning | 08:00
Good night | 23:00

Messages must be friendly and informal.

---

# 4. News Aggregation

News sources are stored in database.

Categories:

- Georgia
- Belarus
- World

Examples:

Georgia
- agenda.ge
- civil.ge

Belarus
- onliner.by
- zerkalo.io

World
- BBC
- Reuters

The bot fetches news and uses AI to summarize.

---

# 5. Currency Rates

Track exchange rates:

| Base | Target |
|----|----|
EUR | GEL
USD | GEL
RUB | GEL
EUR | BYN
USD | BYN
RUB | BYN

Rates stored daily.

Bot reports:

- today's rate
- yesterday's rate
- change

---

# 6. AI Integration

Two AI providers:

Primary
- Gemini API

Fallback
- OpenAI ChatGPT

Uses:

- news summaries
- chat responses
- conversational interaction

---

# Database

Database: PostgreSQL

Schema managed via migrations.

---

# Suggested Tables

## chat_members

chat_id
user_id
username
display_name
is_active

---

## daily_activity

chat_id
user_id
date
message_count
last_message_ts

---

## currency_rates

base_currency
target_currency
date
rate

---

## news_sources

id
name
country
url
enabled

---

## news_items

source_id
title
url
published_at
content_hash

---

# Architecture

app/
bot/
handlers.py
scheduler.py
formatting.py

core/
config.py
models.py
services/
activity_service.py
news_service.py
currency_service.py
ai_service.py

integrations/
telegram/
news/
rates/
ai/
gemini_client.py
openai_client.py

storage/
repo.py
pg_repo.py
migrations/

main.py

---

# Configuration

Example `.env`

BOT_TOKEN=
TARGET_CHAT_ID=

GEMINI_API_KEY=
OPENAI_API_KEY=

POSTGRES_URL=

---

# MVP Scope

Initial version must include:

- Telegram bot integration
- PostgreSQL
- migrations
- morning/night messages
- activity tracking
- news summary
- currency rates
- AI replies on mention

---

# Future Enhancements

Possible future features:

- reminders
- birthdays
- family calendar
- voice summaries
- AI daily digest
