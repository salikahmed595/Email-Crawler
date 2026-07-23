"""
CrawlResult ORM model.
Stores metadata about each individual crawl operation per page/URL.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company


class CrawlResult(Base, TimestampMixin):
    """
    Records the result of crawling a specific URL for a company.
    Provides full audit trail of what was fetched and how.
    """

    __tablename__ = "crawl_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)  # After redirects

    # Request metadata
    engine_used: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # http / playwright / pdf / ocr
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_length: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Performance
    crawl_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    crawled_at: Mapped[datetime] = mapped_column(nullable=False)

    # Outcome
    success: Mapped[bool] = mapped_column(nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    emails_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Redirect chain
    redirect_chain: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Technology fingerprints detected on this page
    tech_stack: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Headers captured
    response_headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="crawl_results")

    __table_args__ = (
        Index("ix_crawl_results_company_url", "company_id", "url"),
        Index("ix_crawl_results_engine", "engine_used"),
    )

    def __repr__(self) -> str:
        return (
            f"<CrawlResult id={self.id} url={self.url!r} "
            f"engine={self.engine_used!r} success={self.success}>"
        )
