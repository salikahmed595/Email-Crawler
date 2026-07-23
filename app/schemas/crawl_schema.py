"""Pydantic schemas for crawl jobs and results."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrawlJobCreate(BaseModel):
    """Request to create a new crawl job."""

    domain: str
    company_id: uuid.UUID
    priority: int = Field(default=5, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrawlJobStatus(BaseModel):
    """Status of a crawl job."""

    job_id: str
    domain: str
    status: str  # queued / running / completed / failed / dead
    retry_count: int
    enqueued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class ImportRequest(BaseModel):
    """Request to import a CSV file and start crawling."""

    filename: str
    total_rows: int
    queued_jobs: int
    skipped_rows: int
    import_id: str


class CrawlSummary(BaseModel):
    """Summary of a completed crawl for a single company."""

    company_id: str
    domain: str
    pages_crawled: int
    emails_found: int
    emails_valid: int
    duration_ms: float
    engines_used: list[str]
    status: str
