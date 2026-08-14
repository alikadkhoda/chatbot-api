from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.prompts import DEFAULT_SYSTEM_PROMPT
from app.schemas.llm_provider import AIProvider


class AISetting(BaseModel):
    provider: AIProvider = AIProvider.OLLAMA

    gemini_api_key: str

    default_model: str = "qwen3"
    ollama_host: str = "http://localhost:11434"

    context_window: int = 8192
    reserve_tokens: int = 2048
    summary_trigger_tokens: int = 6000

    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    @field_validator("system_prompt", mode="before")
    @classmethod
    def use_default_system_prompt(cls, value: str | None) -> str:
        if value is None or not value.strip():
            return DEFAULT_SYSTEM_PROMPT

        return value


class Settings(BaseSettings):
    app_name: str
    app_version: str

    debug: bool = False
    sql_echo: bool = False

    database_url: str

    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"
    ai: AISetting

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, env_nested_delimiter="__"
    )


settings = Settings()
