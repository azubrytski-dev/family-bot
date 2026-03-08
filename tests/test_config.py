from app.core.config import AppConfig


def test_weather_cities_parsing(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("TARGET_CHAT_ID", "123")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("WEATHER_CITIES", "Minsk, Tbilisi, Batumi")

    cfg = AppConfig()  # type: ignore[call-arg]

    assert cfg.weather_cities == ["Minsk", "Tbilisi", "Batumi"]
    assert cfg.target_chat_id == 123

