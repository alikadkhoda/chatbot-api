from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.prompts import DEFAULT_SYSTEM_PROMPT
from app.schemas.llm_provider import AIProvider


class AISetting(BaseModel):
    provider: AIProvider = AIProvider.OLLAMA

    gemini_api_key: str

    default_model: str = "qwen3"
    ollama_host: str = "http://localhost:11434"

    request_timeout_seconds: float = 60.0

    context_window: int = 8192
    reserve_tokens: int = 2048
    summary_trigger_tokens: int = 6000

    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    max_requests_per_minute: int = 20
    max_requests_per_day: int = 200

    max_tokens_per_request: int = 6000
    max_tokens_per_day: int = 100_000
    max_output_tokens: int = 2048

    max_estimated_cost_per_day: float = Field(default=0.0, ge=0)

    input_cost_per_1k_tokens: float = Field(default=0.0, ge=0)
    output_cost_per_1k_tokens: float = Field(default=0.0, ge=0)

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

    redis_url: str

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, env_nested_delimiter="__"
    )


settings = Settings()
