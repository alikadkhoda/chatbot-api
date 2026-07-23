from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
