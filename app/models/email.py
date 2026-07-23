"""
Email ORM model.
Every discovered email is stored with full provenance metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company


class Email(Base, TimestampMixin):
    """
    Represents a discovered and validated email address.

    Every email must carry:
    - source: where it came from (url, pdf, schema, etc.)
    - method: how it was found (mailto, regex, base64, cloudflare, etc.)
    - page: which page it was found on
    - confidence: 0-100 deterministic score
    - timestamp: when it was discovered
    """

    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Core fields
    address: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    address_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # SHA-256 for dedup

    # Provenance — required for all emails
    source: Mapped[str] = mapped_column(
        String(2048), nullable=False
    )  # URL or file path where found
    method: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # mailto / regex / base64 / cloudflare / schema / js / comment / pdf / ocr
    page: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(nullable=False)

    # Confidence
    confidence: Mapped[int] = mapped_column(nullable=False, default=0)  # 0-100

    # Validation results
    is_valid_syntax: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_valid_domain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mx_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_disposable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_role_based: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Status
    validation_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
        # Values: pending, valid, invalid, uncertain
    )

    # Additional metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="emails")

    __table_args__ = (
        Index("ix_emails_address_company", "address", "company_id"),
        Index("ix_emails_hash_company", "address_hash", "company_id", unique=True),
        Index("ix_emails_confidence", "confidence"),
        Index("ix_emails_valid", "validation_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Email id={self.id} address={self.address!r} "
            f"confidence={self.confidence} method={self.method!r}>"
        )
