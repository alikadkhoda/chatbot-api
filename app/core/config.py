from enum import StrEnum

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AIProvider(StrEnum):
    GEMINI = "gemini"
    OLLAMA = "ollama"


class AISetting(BaseModel):
    provider: AIProvider = AIProvider.OLLAMA
    gemini_api_key: str
    default_model: str = "qwen3"
    ollama_host: str = "http://localhost:11434"


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
