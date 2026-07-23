"""
Company ORM model.
Represents a single business being crawled.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.email import Email
    from app.models.crawl_result import CrawlResult


class Company(Base, TimestampMixin):
    """
    Represents a business entity being processed through the pipeline.
    Stores all discovered metadata about the company.
    """

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Pipeline status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        # Values: pending, crawling, extracting, validating, completed, failed, skipped
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)

    # Enriched business data (stored as JSONB for flexibility)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 3-4 line "what they do" summary built from real crawled content
    # (meta/schema description + services), optionally polished by AI —
    # see app/services/summary_service.py. Never fabricated from nothing.
    business_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    phone_numbers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    social_links: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    technologies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    services: Mapped[list | None] = mapped_column(JSON, nullable=True)
    opening_hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    team_members: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Website issue detection (deterministic — see app/services/issue_detector.py)
    website_issues: Mapped[list | None] = mapped_column(JSON, nullable=True)
    issue_summary: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Source metadata
    source_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_row: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    emails: Mapped[list["Email"]] = relationship(
        "Email",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    crawl_results: Mapped[list["CrawlResult"]] = relationship(
        "CrawlResult",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_companies_status_domain", "status", "domain"),
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} domain={self.domain!r} status={self.status!r}>"
