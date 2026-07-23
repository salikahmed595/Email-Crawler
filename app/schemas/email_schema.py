"""
Pydantic schemas for Email data.

Every extracted value carries: value, confidence, source, method, timestamp.
This is enforced at the schema level — never plain strings.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class ExtractedValue(BaseModel):
    """
    Generic container for any extracted datum.
    Every extraction must return this — never a plain string.
    """

    value: str
    confidence: int = Field(ge=0, le=100, description="Confidence score 0-100")
    source: str = Field(description="URL or file path where value was found")
    method: str = Field(description="Extraction method used")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"frozen": True}


class EmailExtracted(BaseModel):
    """Raw extracted email before validation."""

    address: str
    confidence: int = Field(ge=0, le=100)
    source: str
    method: str
    page: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("address", mode="before")
    @classmethod
    def normalize_address(cls, v: str) -> str:
        return v.strip().lower()


class EmailValidationResult(BaseModel):
    """Result of the 10-stage email validation pipeline."""

    address: str
    is_valid_syntax: bool = False
    is_valid_domain: bool = False
    mx_valid: bool = False
    smtp_valid: bool | None = None
    is_disposable: bool = False
    is_role_based: bool = False
    is_duplicate: bool = False
    confidence: int = Field(ge=0, le=100, default=0)
    validation_status: str = "pending"
    notes: list[str] = Field(default_factory=list)


class EmailRead(BaseModel):
    """Schema for reading an email record from the database."""

    id: uuid.UUID
    company_id: uuid.UUID
    address: str
    source: str
    method: str
    page: str | None
    confidence: int
    is_valid_syntax: bool
    is_valid_domain: bool
    mx_valid: bool
    smtp_valid: bool | None
    is_disposable: bool
    is_role_based: bool
    is_duplicate: bool
    validation_status: str
    discovered_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailCreate(BaseModel):
    """Schema for creating an email record."""

    company_id: uuid.UUID
    address: str
    address_hash: str
    source: str
    method: str
    page: str | None = None
    confidence: int = 0
    discovered_at: datetime
    is_valid_syntax: bool = False
    is_valid_domain: bool = False
    mx_valid: bool = False
    smtp_valid: bool | None = None
    is_disposable: bool = False
    is_role_based: bool = False
    is_duplicate: bool = False
    validation_status: str = "pending"
    notes: str | None = None
