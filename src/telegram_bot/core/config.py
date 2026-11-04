from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    telegram_bot_token: str
    openai_api_key: str

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_bot"
    )

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    app_env: str = "development"

    webhook_base_url: str = ""
    webhook_path: str = "/telegram/webhook"

    port: int = 8000

    model_name: str = "gpt-4o-mini"
    model_temperature: float = 0.2
    model_max_tokens: int = 1000
    model_timeout: int = 30

    admin_username: str = "admin"
    admin_password: str = "admin"
    pinecone_api_key: str
    pinecone_index_name: str

    embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    smtp_from: str

    llm_model_input_cost: Decimal = 0.15
    llm_model_output_cost: Decimal = 0.60


@lru_cache
def get_settings() -> Settings:
    return Settings()
