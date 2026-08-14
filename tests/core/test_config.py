from app.core.config import AISetting
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
