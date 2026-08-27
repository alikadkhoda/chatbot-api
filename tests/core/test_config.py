from app.core.config import AISetting, Settings
from app.core.prompts import DEFAULT_SYSTEM_PROMPT


def test_empty_system_prompt_uses_default():
    settings = AISetting(
        gemini_api_key="test",
        system_prompt="",
    )

    assert settings.system_prompt == DEFAULT_SYSTEM_PROMPT


def test_whitespace_system_prompt_uses_default():
    settings = AISetting(
        gemini_api_key="test",
        system_prompt="   ",
    )

    assert settings.system_prompt == DEFAULT_SYSTEM_PROMPT


def test_custom_system_prompt_is_preserved():
    settings = AISetting(
        gemini_api_key="test",
        system_prompt="You are a banking assistant.",
    )

    assert settings.system_prompt == ("You are a banking assistant.")


def test_read_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("APP_NAME", "test")
    monkeypatch.setenv("APP_VERSION", "test")
    monkeypatch.setenv("DATABASE_URL", "test")
    monkeypatch.setenv("SECRET_KEY", "test")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("SYSTEM_PROMPT", "You are a banking assistant.")
    settings = Settings()

    assert settings.redis_url == "redis://localhost:6379/0"
