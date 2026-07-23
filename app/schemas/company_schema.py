"""Pydantic schemas for Company data."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class CompanyCreate(BaseModel):
    """Schema for creating a new company from CSV import."""

    name: str | None = None
    domain: str
    website: str | None = None
    source_file: str | None = None
    source_row: int | None = None

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, v: str) -> str:
        v = v.strip().lower()
        # Strip protocol if accidentally included
        for prefix in ("https://", "http://", "www."):
            if v.startswith(prefix):
                v = v[len(prefix):]
        return v.rstrip("/")


class CompanyRead(BaseModel):
    """Full company record with all enriched data."""

    id: uuid.UUID
    name: str | None
    domain: str
    website: str | None
    status: str
    description: str | None
    industry: str | None
    category: str | None
    address: dict[str, Any] | None
    phone_numbers: list[Any] | None
    social_links: dict[str, Any] | None
    technologies: list[Any] | None
    services: list[Any] | None
    opening_hours: dict[str, Any] | None
    team_members: list[Any] | None
    retry_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyListItem(BaseModel):
    """Lightweight company record for list views."""

    id: uuid.UUID
    domain: str
    name: str | None
    status: str
    email_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyExport(BaseModel):
    """Schema for JSON export — includes emails."""

    id: str
    name: str | None
    domain: str
    website: str | None
    status: str
    description: str | None
    industry: str | None
    address: dict[str, Any] | None
    phone_numbers: list[Any] | None
    social_links: dict[str, Any] | None
    technologies: list[Any] | None
    services: list[Any] | None
    emails: list[dict[str, Any]] = Field(default_factory=list)
    crawled_at: str | None = None
