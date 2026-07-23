"""
CrawlJob dataclass — represents a unit of work in the queue.
Stateless: all state lives in Redis, not in the worker.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CrawlJob:
    """
    A single crawl job for one company domain.

    Fields:
        job_id      — Unique job identifier
        company_id  — UUID of the company record
        domain      — Domain to crawl
        priority    — 1 (highest) to 10 (lowest)
        retry_count — How many times this job has been retried
        enqueued_at — When the job was first added to the queue
        metadata    — Any additional context
    """

    company_id: str
    domain: str
    priority: int = 5
    retry_count: int = 0
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enqueued_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "company_id": self.company_id,
            "domain": self.domain,
            "priority": self.priority,
            "retry_count": self.retry_count,
            "enqueued_at": self.enqueued_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CrawlJob":
        return cls(
            job_id=data["job_id"],
            company_id=data["company_id"],
            domain=data["domain"],
            priority=data.get("priority", 5),
            retry_count=data.get("retry_count", 0),
            enqueued_at=data.get("enqueued_at", datetime.now(timezone.utc).isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ValidationJob:
    """A job to validate all emails for a company."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str = ""
    email_ids: list[str] = field(default_factory=list)
    enqueued_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "company_id": self.company_id,
            "email_ids": self.email_ids,
            "enqueued_at": self.enqueued_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationJob":
        return cls(
            job_id=data["job_id"],
            company_id=data["company_id"],
            email_ids=data.get("email_ids", []),
            enqueued_at=data.get("enqueued_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class ExportJob:
    """A job to export results to JSON."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    output_path: str = "output/results.json"
    min_confidence: int = 0
    enqueued_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "output_path": self.output_path,
            "min_confidence": self.min_confidence,
            "enqueued_at": self.enqueued_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExportJob":
        return cls(
            job_id=data["job_id"],
            output_path=data.get("output_path", "output/results.json"),
            min_confidence=data.get("min_confidence", 0),
            enqueued_at=data.get("enqueued_at", datetime.now(timezone.utc).isoformat()),
        )
