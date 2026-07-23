"""
Company repository — all database operations for Company model.
No raw SQL in services. All DB logic lives here.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.schemas.company_schema import CompanyCreate


class CompanyRepository:
    """
    Repository for Company database operations.
    All queries use specific column selects — never SELECT *.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: CompanyCreate) -> Company:
        """Insert a new company. Skips if domain already exists."""
        company = Company(
            name=data.name,
            domain=data.domain,
            website=data.website,
            source_file=data.source_file,
            source_row=data.source_row,
            status="pending",
        )
        self._session.add(company)
        await self._session.flush()
        return company

    async def get_by_id(self, company_id: uuid.UUID) -> Company | None:
        """Fetch a single company by ID."""
        stmt = select(Company).where(Company.id == company_id).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_domain(self, domain: str) -> Company | None:
        """Fetch a company by domain (unique index)."""
        stmt = select(Company).where(Company.domain == domain).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, data: CompanyCreate) -> tuple[Company, bool]:
        """
        Get existing company by domain or create new one.
        Returns (company, created) tuple.
        """
        existing = await self.get_by_domain(data.domain)
        if existing:
            return existing, False
        company = await self.create(data)
        return company, True

    async def update_status(
        self,
        company_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update company processing status."""
        values: dict[str, Any] = {"status": status}
        if error_message is not None:
            values["error_message"] = error_message
        stmt = (
            update(Company)
            .where(Company.id == company_id)
            .values(**values)
        )
        await self._session.execute(stmt)

    async def update_metadata(
        self,
        company_id: uuid.UUID,
        metadata: dict[str, Any],
    ) -> None:
        """Update company enrichment metadata fields."""
        stmt = (
            update(Company)
            .where(Company.id == company_id)
            .values(**metadata)
        )
        await self._session.execute(stmt)

    async def increment_retry(self, company_id: uuid.UUID) -> None:
        """Increment the retry counter for a company."""
        stmt = (
            update(Company)
            .where(Company.id == company_id)
            .values(retry_count=Company.retry_count + 1)
        )
        await self._session.execute(stmt)

    async def list_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Company]:
        """Fetch companies with a given status, paginated."""
        stmt = (
            select(Company)
            .where(Company.status == status)
            .order_by(Company.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        """Count companies grouped by status."""
        stmt = select(Company.status, func.count(Company.id)).group_by(Company.status)
        result = await self._session.execute(stmt)
        return dict(result.all())

    async def list_all(self, limit: int = 1000, offset: int = 0) -> list[Company]:
        """List all companies, paginated."""
        stmt = (
            select(Company)
            .order_by(Company.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
