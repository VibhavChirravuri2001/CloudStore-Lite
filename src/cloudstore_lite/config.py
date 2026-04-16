from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CloudStore-Lite"
    database_url: str = "postgresql+psycopg://cloudstore:cloudstore@postgres:5432/cloudstore"
    storage_root: Path = Path("storage")
    api_key: str = Field(default="dev-api-key", min_length=8)
    signed_url_secret: str = Field(default="replace-me-for-production", min_length=16)
    signed_url_ttl_seconds: int = Field(default=900, ge=60, le=86400)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CLOUDSTORE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

