"""
Export service — exports all crawl results to structured JSON.
Output format: one JSON array of company records, each with their emails.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import aiofiles

from app.config import get_settings
from app.logging import get_logger
from app.storage.database import get_session
from app.storage.repositories.company_repo import CompanyRepository
from app.storage.repositories.email_repo import EmailRepository

logger = get_logger(__name__)


class ExportService:
    """
    Exports company + email data to structured JSON files.
    Uses streaming/batched reads to avoid OOM on large datasets.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def export_to_json(
        self,
        output_path: str | None = None,
        min_confidence: int = 0,
        batch_size: int = 500,
    ) -> str:
        """
        Export all companies and their emails to a JSON file.
        Returns the output file path.
        """
        if not output_path:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                self._settings.output_dir, f"export_{timestamp}.json"
            )

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        records: list[dict[str, Any]] = []
        offset = 0

        while True:
            async with get_session() as session:
                company_repo = CompanyRepository(session)
                email_repo = EmailRepository(session)

                companies = await company_repo.list_all(
                    limit=batch_size, offset=offset
                )
                if not companies:
                    break

                for company in companies:
                    emails = await email_repo.get_by_company(
                        company.id,
                        min_confidence=min_confidence,
                    )

                    record: dict[str, Any] = {
                        "id": str(company.id),
                        "name": company.name,
                        "domain": company.domain,
                        "website": company.website,
                        "status": company.status,
                        "description": company.description,
                        "business_summary": company.business_summary,
                        "state": (company.address or {}).get("state")
                        if isinstance(company.address, dict)
                        else None,
                        "industry": company.industry,
                        "category": company.category,
                        "address": company.address,
                        "phone_numbers": company.phone_numbers,
                        "social_links": company.social_links,
                        "technologies": company.technologies,
                        "services": company.services,
                        "opening_hours": company.opening_hours,
                        "team_members": company.team_members,
                        "website_issues": company.website_issues,
                        "issue_summary": company.issue_summary,
                        "crawled_at": company.updated_at.isoformat()
                        if company.updated_at
                        else None,
                        "emails": [
                            {
                                "address": e.address,
                                "confidence": e.confidence,
                                "source": e.source,
                                "method": e.method,
                                "page": e.page,
                                "validation_status": e.validation_status,
                                "mx_valid": e.mx_valid,
                                "is_disposable": e.is_disposable,
                                "is_role_based": e.is_role_based,
                                "discovered_at": e.discovered_at.isoformat(),
                            }
                            for e in emails
                        ],
                    }
                    records.append(record)

            offset += batch_size

        # Write to file
        async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(records, indent=2, ensure_ascii=False))

        logger.info(
            "Export complete",
            output_path=output_path,
            total_companies=len(records),
            total_emails=sum(len(r["emails"]) for r in records),
        )
        return output_path

    async def get_company_export(self, company_id: str) -> dict[str, Any] | None:
        """Export a single company record with its emails."""
        import uuid

        try:
            cid = uuid.UUID(company_id)
        except ValueError:
            return None

        async with get_session() as session:
            company_repo = CompanyRepository(session)
            email_repo = EmailRepository(session)

            company = await company_repo.get_by_id(cid)
            if not company:
                return None

            emails = await email_repo.get_by_company(cid)

        return {
            "id": str(company.id),
            "name": company.name,
            "domain": company.domain,
            "website": company.website,
            "status": company.status,
            "description": company.description,
            "business_summary": company.business_summary,
            "state": (company.address or {}).get("state")
            if isinstance(company.address, dict)
            else None,
            "address": company.address,
            "phone_numbers": company.phone_numbers,
            "social_links": company.social_links,
            "technologies": company.technologies,
            "services": company.services,
            "website_issues": company.website_issues,
            "issue_summary": company.issue_summary,
            "emails": [
                {
                    "address": e.address,
                    "confidence": e.confidence,
                    "source": e.source,
                    "method": e.method,
                    "page": e.page,
                    "validation_status": e.validation_status,
                    "mx_valid": e.mx_valid,
                    "is_disposable": e.is_disposable,
                    "is_role_based": e.is_role_based,
                    "discovered_at": e.discovered_at.isoformat(),
                }
                for e in emails
            ],
        }
