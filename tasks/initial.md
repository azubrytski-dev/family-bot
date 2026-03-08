Here is a clean prompt you can use to start a new project in Cursor / Copilot / ChatGPT.

⸻

Prompt

You are a senior Python backend engineer and system designer.

Build a Telegram bot for one specific family group chat only.

Goal

Create a production-ready Telegram bot that works only with one configured Telegram group chat and acts as a daily family assistant.

The bot should:
	•	monitor whether each family member has written at least one message today;
	•	notify the chat if someone has not written anything today;
	•	when everyone has written, send a positive “good morning / all present” style message;
	•	send scheduled morning and night messages by Minsk time;
	•	provide weather, news, and currency updates in Russian;
	•	track day-by-day metrics and historical values in PostgreSQL;
	•	use database migrations for schema changes;
	•	use AI integration for summaries / bot replies.

⸻

Main requirements

1. Telegram bot scope
	•	Bot works with one single configured chat only.
	•	Ignore all other chats.
	•	Store configured TARGET_CHAT_ID in config.
	•	If bot is mentioned in the chat, it should answer with an AI-generated response.

2. Daily activity tracking
	•	Track all users in the target chat.
	•	For each day, determine whether each member wrote at least one message.
	•	At a configured check time, if someone has not written today, send a message listing those users.
	•	If everyone has written, send a friendly positive message.

3. Scheduled messages
	•	Send:
	•	Good morning at 08:00 Minsk time
	•	Good night at 23:00 Minsk time
	•	Use correct timezone handling.
	•	Messages must be in Russian.

4. Weather
	•	Weather cities are defined in config.
	•	Example: Minsk, Tbilisi, Batumi, etc.
	•	Bot should post weather summary for configured cities.
	•	Weather should be tracked historically by day:
	•	today
	•	yesterday
	•	one week ago
	•	Store weather snapshots in PostgreSQL.

5. News
	•	Bot should gather news from configured sources.
	•	Sources must be stored in database.
	•	Must support migrations for adding/changing/removing sources.
	•	Categories:
	•	Georgia news
	•	Belarus news
	•	World news
	•	Bot should use AI to summarize collected news in Russian.

6. Currency exchange rates
	•	Track rates for:
	•	EUR -> GEL
	•	USD -> GEL
	•	RUB -> GEL
	•	EUR -> BYN
	•	USD -> BYN
	•	RUB -> BYN
	•	Store historical daily values in PostgreSQL.
	•	Bot should be able to report:
	•	current rate
	•	yesterday’s rate
	•	difference vs yesterday
	•	difference vs 7 days ago

7. AI integration
	•	Primary AI provider: Gemini API
	•	Fallback provider: OpenAI / ChatGPT
	•	Requirements:
	•	abstract AI provider behind interface
	•	if Gemini fails, automatically fallback to ChatGPT
	•	use AI for:
	•	news summaries
	•	smart replies when bot is mentioned
	•	optional friendly daily commentary

8. Database
	•	Database: PostgreSQL
	•	Use proper repository / DAO abstraction.
	•	Business logic must not depend directly on PostgreSQL specifics.
	•	Use migrations for schema updates.

9. Language
	•	All user-facing messages must be in Russian.
	•	Code comments and code structure must be in English.

⸻

Technical requirements
	•	Language: Python
	•	Prefer modern Python (3.12+)
	•	Use clean architecture / layered structure
	•	Use SOLID where appropriate
	•	Use async where it makes sense
	•	Use environment-based config
	•	Use structured logging
	•	Bot must be resilient to API failures and missing data
	•	If weather/news/AI fails, bot should degrade gracefully

⸻

Suggested architecture

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
      weather_service.py
      news_service.py
      currency_service.py
      ai_service.py
  integrations/
    telegram/
    weather/
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


⸻

Data model ideas

chat_members
	•	chat_id
	•	user_id
	•	username
	•	display_name
	•	is_active

daily_activity
	•	chat_id
	•	user_id
	•	activity_date
	•	message_count
	•	last_message_ts

weather_snapshots
	•	city
	•	snapshot_date
	•	temperature
	•	condition
	•	raw_payload_json

currency_rates
	•	base_currency
	•	target_currency
	•	rate_date
	•	rate_value

news_sources
	•	id
	•	source_name
	•	source_type
	•	country
	•	url
	•	is_enabled

news_items
	•	source_id
	•	published_at
	•	title
	•	url
	•	content_hash

bot_state
	•	chat_id
	•	last_morning_ts
	•	last_night_ts
	•	last_activity_check_ts
	•	last_news_digest_ts

⸻

MVP scope

Implement only MVP first:
	1.	Telegram bot for one configured group chat
	2.	PostgreSQL + migrations
	3.	Morning message at 08:00 Minsk time
	4.	Night message at 23:00 Minsk time
	5.	Daily activity tracking:
	•	who wrote today
	•	who did not
	•	“everyone wrote” message
	6.	Weather from config cities
	7.	News collection from DB-configured sources
	8.	AI summarization:
	•	primary Gemini
	•	fallback ChatGPT
	9.	Currency rates:
	•	EUR/USD/RUB to GEL and BYN
	•	compare with yesterday
	10.	Mention bot in chat -> AI answer in Russian

⸻

Additional notes
	•	Find and preconfigure several news source examples for:
	•	Georgia
	•	Belarus
	•	world news
	•	Add configuration for cities and target currencies
	•	Keep project easy to extend
	•	Generate:
	1.	folder structure
	2.	architecture overview
	3.	PostgreSQL schema
	4.	migration strategy
	5.	config model
	6.	MVP implementation plan by phases
	7.	story points / effort estimate

⸻

Expected output

Return:
	1.	concise architecture
	2.	phased implementation plan
	3.	database schema
	4.	folder/file structure
	5.	config example
	6.	migration approach
	7.	code skeletons for key modules

⸻

If you want, I can also convert this into:
	•	a shorter Cursor prompt
	•	a technical spec markdown
	•	or a phased implementation backlog with story points.