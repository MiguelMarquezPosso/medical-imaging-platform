"""Configuration loaded from environment variables.

No secret, URL or sensitive value is hard-coded — every field is sourced from
the environment so that the same image can run in any environment.
"""

from __future__ import annotations

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

    APP_NAME: str = "medical-imaging-service"
    APP_ENV: Literal["development", "staging", "production"] = "production"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    PUBLIC_BASE_URL: AnyHttpUrl

    CORS_ALLOWED_ORIGINS: str = ""

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DB_SCHEMA: str = ""  # if set, becomes first entry in postgres search_path

    # JWT — shared signing key with Auth Service
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str
    JWT_AUDIENCE: str

    # DICOMweb upstream (Orthanc behind a private tunnel)
    DICOMWEB_BASE_URL: str
    DICOMWEB_AUTH_TYPE: Literal["none", "basic", "bearer"] = "none"
    DICOMWEB_USERNAME: str = ""
    DICOMWEB_PASSWORD: str = ""
    DICOMWEB_BEARER_TOKEN: str = ""
    DICOMWEB_VERIFY_TLS: bool = True
    DICOMWEB_TIMEOUT_SECONDS: int = 60

    ORTHANC_TUNNEL_KIND: str = "wireguard"

    # Sync ingestion
    SYNC_AES_KEY_BASE64: str
    SYNC_HMAC_KEY_BASE64: str = ""
    SYNC_MAX_UPLOAD_BYTES: int = 1_073_741_824  # 1 GiB

    # Storage
    STORAGE_BACKEND: Literal["filesystem", "s3"] = "filesystem"
    STORAGE_ROOT: str = "/data/dicom"
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = ""
    S3_REGION: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""

    # Swagger UI / OpenAPI
    ENABLE_DOCS: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.CORS_ALLOWED_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @field_validator("JWT_SECRET_KEY", "SYNC_AES_KEY_BASE64")
    @classmethod
    def _no_placeholder(cls, v: str) -> str:
        if v.startswith("change-me"):
            raise ValueError("This secret must be replaced with a real value")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
