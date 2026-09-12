from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    telegram_bot_token: str
    openai_api_key: str
    database_url:str 
    jwt_secret_key:str 
    jwt_algorithm:str
    access_token_expire_minuutes:str
    refresh_token_expire_days:str

    app_env: str = "development"

    webhook_base_url: str = ""
    webhook_path: str = "/telegram/webhook"

    port: int = 8000

    model_name: str = "gpt-4o-mini"

    model_temperature: float = 0.2

    model_max_tokens: int = 1000

    model_timeout: int = 30

    admin_useranme:str
    admin_password:str

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()