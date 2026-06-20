Faminy Bot — AI Weather Summary Feature

Goal

Add a simple weather feature for 2 configurable cities.

The flow must be:

1. load enabled weather cities from DB config
2. fetch current weather from a free external API
3. build a weather description prompt
4. pass structured weather data into AI together with:
    * bot system prompt
    * weather description prompt
5. return a short Russian AI-generated message with:
    * simple weather summary
    * suggestion what to wear

Also add a test bot command to trigger this logic manually.

⸻

Required flow

Runtime flow

config -> api_fetch -> prompt_build -> AI_generate -> Telegram_message

Details

1. Config

Weather cities must come from the database, not hardcoded.

Use a generic configuration table.

Suggested schema:

* id
* parameter
* value
* is_enabled
* created_at
* updated_at

Suggested usage:

* parameter = 'weather.city'
* value = 'Minsk'
* is_enabled = true
* parameter = 'weather.city'
* value = 'Tbilisi'
* is_enabled = true

Recommended constraints:

* unique index on (parameter, value)
* index on parameter

This is enough for the first version.

⸻

2. API fetch

Use a free weather API.

Recommended provider: Open-Meteo

Use Open-Meteo as the default provider because:

* no API key required for non-commercial basic usage
* simple JSON API
* geocoding API available
* current weather and forecast support
* free usage with documented limits for non-commercial use (Open Meteo)

Open-Meteo states:

* no API key required
* no sign-up for the basic free path
* simple HTTP GET JSON API
* non-commercial use up to 10,000 daily API calls free (Open Meteo)

Implementation can use:

* geocoding by city name
* then current weather / short forecast by coordinates

Do not overdesign provider abstraction. One provider is enough for now.

⸻

Feature behavior

The bot should not return raw technical weather data directly.

Instead:

1. fetch structured weather data for both configured cities
2. build a small normalized internal weather object
3. generate AI response in Russian using:
    * existing bot system prompt
    * additional weather description prompt

Expected AI output style

* short
* simple
* family-friendly
* in Russian
* not too detailed
* mention both cities
* include practical clothing suggestion

Example style:

* “В Минске прохладно и облачно, около +6°C — лучше надеть куртку. В Тбилиси теплее, около +14°C, можно обойтись лёгкой верхней одеждой.”

⸻

Prompting requirements

Base prompt

Reuse the existing bot system prompt.

Add weather-specific prompt

Add a weather description prompt like:

* describe weather in Russian
* keep it short and practical
* avoid too much detail
* summarize the weather for the configured cities
* add a short suggestion what to wear
* do not invent data that is not present
* do not make medical or dangerous recommendations
* keep total response compact

The final AI input should be something like:

* system prompt
* weather instruction prompt
* structured weather payload

⸻

Bot command

Add a test command that triggers the whole weather pipeline manually.

Suggested command:

* /weather_test

Behavior:

* loads enabled weather cities from DB
* fetches weather
* runs AI formatting
* sends final Russian message to the chat

This is a test/integration command for now.
It can later be reused inside /info or scheduler jobs.

⸻

Architecture

Keep the implementation simple and modular.

Suggested modules

Integration layer

* app/integrations/weather/client.py

Responsibilities:

* call Open-Meteo geocoding
* call Open-Meteo forecast/current weather endpoint
* return normalized Python structures

Service layer

* app/core/services/weather_service.py

Responsibilities:

* load enabled cities from config repository
* fetch weather for each city
* build normalized weather payload
* build AI prompt input
* call AI service
* return final Russian text

Storage layer

Extend existing repository layer with:

* read config values for weather.city
* optional persistence of raw weather snapshots if easy
* snapshot persistence is optional for first iteration

⸻

Data model

Mandatory

Generic config table:

* id
* parameter
* value
* is_enabled
* timestamps

Optional for first iteration

Weather snapshot table:

* id
* city
* snapshot_at
* temperature_c
* condition_text
* wind_speed
* raw_payload

Snapshot persistence is nice to have, but not required if it slows down the feature.

Main priority is:

* config-driven cities
* working API fetch
* AI-generated Russian weather summary

⸻

Output expectations

The output should be a simple weather forecast, not detailed meteorology.

Do:

* current weather or very short forecast
* 1–2 concise sentences
* practical clothing suggestion

Do not:

* dump raw JSON
* produce long explanation
* mention too many metrics
* overcomplicate with pressure/humidity unless needed

⸻

Error handling

* if one city fails, still return result for the other city
* if all weather fetches fail, return a short Russian fallback message
* if AI formatting fails, fallback to a simple deterministic Russian text summary
* weather fetch failures must not crash the bot

⸻

Implementation priorities

1. add config table migration
2. add config repository method to load weather.city values
3. implement Open-Meteo client
4. implement weather service orchestration
5. connect weather service to AI service
6. add /weather_test command
7. keep changes minimal and consistent with current architecture

⸻

Non-goals

Do not implement now:

* full weekly forecast
* weather widgets
* admin UI for changing cities
* multiple weather providers
* severe weather alerts
* very detailed historical comparison

⸻

Final recommendation

Implement the first version with:

* generic config table
* weather.city rows
* Open-Meteo
* AI-generated Russian summary
* /weather_test command

That gives a full vertical slice:

DB config -> weather API -> AI prompt -> Telegram output

with minimal complexity and easy future integration into /info or scheduler jobs.