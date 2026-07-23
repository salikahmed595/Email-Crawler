"""
Configuration module — loads all settings from environment variables.
Single source of truth. No hardcoded values anywhere in the codebase.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.
    All values can be overridden via environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_env: Literal["development", "production", "testing"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    secret_key: str = "dev-secret-change-in-production"

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    # Defaults to a local SQLite file — zero setup required. Point this at a
    # Postgres DSN (postgresql+asyncpg://...) to use the Docker/Queue mode instead.
    database_url: str = "sqlite+aiosqlite:///./data/leads.db"

    # -------------------------------------------------------------------------
    # Redis (only used in Docker/Queue mode — not required for the dashboard)
    # -------------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # -------------------------------------------------------------------------
    # Crawler
    # -------------------------------------------------------------------------
    max_workers: int = 4
    http_timeout: int = 15
    max_retries: int = 3
    user_agent: str = "LeadIntelligenceBot/1.0"
    crawl_delay: float = 1.0
    max_pages_per_domain: int = 20
    max_concurrent_domains: int = 10
    request_rate_per_second: float = 5.0

    # -------------------------------------------------------------------------
    # Playwright
    # -------------------------------------------------------------------------
    playwright_enabled: bool = True
    playwright_headless: bool = True
    playwright_timeout: int = 30000
    playwright_browser: Literal["chromium", "firefox", "webkit"] = "chromium"

    # -------------------------------------------------------------------------
    # PDF
    # -------------------------------------------------------------------------
    pdf_enabled: bool = False

    # -------------------------------------------------------------------------
    # OCR
    # -------------------------------------------------------------------------
    ocr_enabled: bool = False

    # -------------------------------------------------------------------------
    # Email Validation
    # -------------------------------------------------------------------------
    smtp_validation_enabled: bool = False
    smtp_timeout: int = 10
    dns_timeout: float = 5.0
    mx_validation_enabled: bool = True

    # -------------------------------------------------------------------------
    # Confidence
    # -------------------------------------------------------------------------
    min_email_confidence: int = 30
    high_confidence_threshold: int = 80

    # -------------------------------------------------------------------------
    # Object Storage
    # -------------------------------------------------------------------------
    object_storage_enabled: bool = False
    minio_url: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "crawl-data"

    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v

    # -------------------------------------------------------------------------
    # Queue
    # -------------------------------------------------------------------------
    crawl_queue_name: str = "crawl_jobs"
    validation_queue_name: str = "validation_jobs"
    export_queue_name: str = "export_jobs"
    dead_letter_queue_name: str = "dead_letter"
    max_job_retries: int = 3
    job_timeout: int = 300

    # -------------------------------------------------------------------------
    # Output
    # -------------------------------------------------------------------------
    output_dir: str = "output"
    export_format: Literal["json", "csv"] = "json"

    # -------------------------------------------------------------------------
    # Local dashboard batch runner
    # -------------------------------------------------------------------------
    concurrent_crawlers: int = 6  # 5-7 recommended: parallel crawling agents
    batch_size: int = 100  # companies processed per batch

    # -------------------------------------------------------------------------
    # OpenAI (optional, last-resort summary polish — off by default)
    # -------------------------------------------------------------------------
    openai_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # -------------------------------------------------------------------------
    # Derived helpers
    # -------------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    Call get_settings() anywhere in the codebase to access configuration.
    """
    return Settings()
