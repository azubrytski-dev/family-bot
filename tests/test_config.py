from app.core.config import AppConfig


def test_minimal_config_loads(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    cfg = AppConfig(_env_file=None)  # type: ignore[call-arg]

    assert cfg.enable_scheduler is True
    assert cfg.enable_activity_tracking is True
    assert cfg.openai_model == "gpt-4.1-nano"


def test_scheduler_and_activity_flags_are_respected(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_SCHEDULER", "false")
    monkeypatch.setenv("ENABLE_ACTIVITY_TRACKING", "false")

    cfg = AppConfig(_env_file=None)  # type: ignore[call-arg]

    assert cfg.enable_scheduler is False
    assert cfg.enable_activity_tracking is False
