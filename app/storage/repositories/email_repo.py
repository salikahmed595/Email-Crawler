"""
Email repository — all database operations for Email model.
Includes deduplication via address_hash unique constraint.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email import Email
from app.schemas.email_schema import EmailCreate


class EmailRepository:
    """
    Repository for Email database operations.
    Deduplication is enforced at DB level via unique constraint on (address_hash, company_id).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_or_skip(self, data: EmailCreate) -> tuple[Email, bool]:
        """
        Insert email if not duplicate (by address_hash + company_id).
        Returns (email, created) — created=False means it was a duplicate.
        """
        # Check for duplicate first
        stmt = (
            select(Email)
            .where(
                Email.address_hash == data.address_hash,
                Email.company_id == data.company_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing, False

        email = Email(**data.model_dump())
        self._session.add(email)
        await self._session.flush()
        return email, True

    async def get_by_id(self, email_id: uuid.UUID) -> Email | None:
        stmt = select(Email).where(Email.id == email_id).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_company(
        self,
        company_id: uuid.UUID,
        min_confidence: int = 0,
        limit: int = 500,
    ) -> list[Email]:
        """
        Get emails for a company, filtered by minimum confidence.
        Limited to avoid full-table loads.
        """
        stmt = (
            select(Email)
            .where(
                Email.company_id == company_id,
                Email.confidence >= min_confidence,
                Email.is_duplicate.is_(False),
            )
            .order_by(Email.confidence.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_validation(
        self,
        email_id: uuid.UUID,
        validation_data: dict,
    ) -> None:
        """Update validation results for an email."""
        from sqlalchemy import update

        stmt = update(Email).where(Email.id == email_id).values(**validation_data)
        await self._session.execute(stmt)

    async def count_by_company(self, company_id: uuid.UUID) -> int:
        """Count emails for a company."""
        stmt = select(func.count(Email.id)).where(
            Email.company_id == company_id,
            Email.is_duplicate.is_(False),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def count_valid(self) -> int:
        """Count globally valid emails."""
        stmt = select(func.count(Email.id)).where(Email.validation_status == "valid")
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def get_all_for_export(
        self,
        min_confidence: int = 0,
        limit: int = 100000,
    ) -> list[Email]:
        """Bulk fetch for export — uses limit to prevent OOM."""
        stmt = (
            select(Email)
            .where(
                Email.confidence >= min_confidence,
                Email.is_duplicate.is_(False),
            )
            .order_by(Email.confidence.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
