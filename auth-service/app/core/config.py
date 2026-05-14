"""Centralised application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "auth-service"
    APP_ENV: Literal["development", "staging", "production"] = "production"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    PUBLIC_BASE_URL: AnyHttpUrl

    CORS_ALLOWED_ORIGINS: str = ""

    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DB_SCHEMA: str = ""  # if set, becomes first entry in postgres search_path

    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    JWT_ISSUER: str
    JWT_AUDIENCE: str

    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SYMBOL: bool = True

    ALLOW_PUBLIC_REGISTRATION: bool = False
    DEFAULT_USER_ROLE: str = "viewer"

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.CORS_ALLOWED_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _check_secret(cls, v: str) -> str:
        if v.startswith("change-me"):
            raise ValueError("JWT_SECRET_KEY must be set to a real secret")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
