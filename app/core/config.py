from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISetting(BaseModel):
    gemini_api_key: str
    default_model: str = "gemini-2.5-flash"


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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
