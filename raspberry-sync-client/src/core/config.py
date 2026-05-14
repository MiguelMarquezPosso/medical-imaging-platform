"""Pi sync client configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    API_BASE_URL: AnyHttpUrl
    API_VERIFY_TLS: bool = True

    SYNC_DEVICE_EMAIL: str
    SYNC_DEVICE_PASSWORD: str
    SYNC_DEVICE_ID: str = Field(max_length=64)

    SYNC_AES_KEY_BASE64: str
    SYNC_HMAC_KEY_BASE64: str = ""

    WATCH_DIR: str
    WATCH_GLOB: str = "*.dcm"
    ARCHIVE_DIR: str
    QUARANTINE_DIR: str
    STATE_DB: str

    RETRY_INTERVAL_SECONDS: int = 30
    CONNECTIVITY_CHECK_INTERVAL: int = 15
    MAX_CONCURRENCY: int = 2

    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
