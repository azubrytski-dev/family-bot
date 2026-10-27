import pytest
from pydantic import ValidationError

from app.core.config import AppConfig


def test_minimal_config_loads(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    cfg = AppConfig(_env_file=None)  # type: ignore[call-arg]

    assert cfg.enable_scheduler is True
    assert cfg.enable_activity_tracking is True
    assert cfg.openai_model == "test-model"


def test_scheduler_and_activity_flags_are_respected(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("ENABLE_SCHEDULER", "false")
    monkeypatch.setenv("ENABLE_ACTIVITY_TRACKING", "false")

    cfg = AppConfig(_env_file=None)  # type: ignore[call-arg]

    assert cfg.enable_scheduler is False
    assert cfg.enable_activity_tracking is False


@pytest.mark.parametrize("model", [None, "", "   "])
def test_openai_model_is_required_and_non_blank(monkeypatch, model):
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    if model is not None:
        monkeypatch.setenv("OPENAI_MODEL", model)

    with pytest.raises(ValidationError) as exc_info:
        AppConfig(_env_file=None)  # type: ignore[call-arg]

    assert any(error["loc"] == ("OPENAI_MODEL",) for error in exc_info.value.errors())


def test_openai_model_loads_from_dotenv_and_environment_overrides_it(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_MODEL=file-model\n", encoding="utf-8")

    assert AppConfig(_env_file=env_file).openai_model == "file-model"  # type: ignore[call-arg]

    monkeypatch.setenv("OPENAI_MODEL", "environment-model")

    assert AppConfig(_env_file=env_file).openai_model == "environment-model"  # type: ignore[call-arg]
