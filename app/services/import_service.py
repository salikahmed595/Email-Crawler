"""
CSV import service — validates, sanitizes, and enqueues companies from CSV input.
Supports columns: company_name, website, domain (auto-detects).
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid
from typing import Any

from app.config import get_settings
from app.logging import get_logger
from app.queue.job import CrawlJob
from app.queue.queue_manager import QueueManager
from app.schemas.company_schema import CompanyCreate
from app.services.maps_resolver import is_maps_url
from app.storage.database import get_session
from app.storage.repositories.company_repo import CompanyRepository
from app.validators.domain_validator import DomainValidator

logger = get_logger(__name__)

# Supported column name aliases
_DOMAIN_COLUMNS = {"domain", "website", "url", "site", "web", "homepage", "website_url"}
_NAME_COLUMNS = {"company_name", "name", "business_name", "company", "organization"}


class ImportService:
    """
    Handles CSV import of company records.
    Validates, sanitizes inputs, creates DB records, enqueues crawl jobs.
    """

    def __init__(self) -> None:
        self._domain_validator = DomainValidator()
        self._settings = get_settings()

    async def import_csv(
        self,
        csv_content: str | bytes,
        source_file: str = "import.csv",
        queue_manager: QueueManager | None = None,
    ) -> dict[str, Any]:
        """
        Parse and import a CSV file.
        Returns import summary: total, queued, skipped, errors.
        """
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode("utf-8", errors="replace")

        reader = csv.DictReader(io.StringIO(csv_content))
        if not reader.fieldnames:
            raise ValueError("CSV file has no headers")

        headers = [h.strip().lower() for h in reader.fieldnames]
        # DictReader keys use the CSV's original header casing, not the
        # lowercased aliases above — map back to the real key for row lookups.
        original_by_lower = dict(zip(headers, reader.fieldnames))

        # Detect domain and name columns
        domain_col_lower = self._detect_column(headers, _DOMAIN_COLUMNS)
        name_col_lower = self._detect_column(headers, _NAME_COLUMNS)

        if not domain_col_lower:
            raise ValueError(
                f"CSV must have a domain/website column. Found: {headers}"
            )

        domain_col = original_by_lower[domain_col_lower]
        name_col = original_by_lower[name_col_lower] if name_col_lower else None

        total = 0
        queued = 0
        skipped = 0
        errors: list[str] = []
        import_id = str(uuid.uuid4())

        for row_num, row in enumerate(reader, start=2):
            total += 1

            raw_domain = (row.get(domain_col) or "").strip()
            raw_name = (row.get(name_col) or "").strip() if name_col else None

            if not raw_domain:
                skipped += 1
                continue

            website_override: str | None = None

            if is_maps_url(raw_domain):
                # This is a Google Maps listing link, not the business's own
                # site — crawling maps.google.com would never find a real
                # business email. Keep each listing as a distinct pending
                # company (a real domain is resolved later, concurrently,
                # during the crawl phase) instead of collapsing every row
                # to "google.com" and silently discarding 99% of the batch.
                domain = self._make_maps_placeholder(raw_domain)
                website_override = raw_domain
            else:
                # Normalize and validate domain
                domain = self._domain_validator.normalize(raw_domain)
                if not domain:
                    logger.warning("Invalid domain in CSV", row=row_num, value=raw_domain)
                    skipped += 1
                    errors.append(f"Row {row_num}: invalid domain '{raw_domain}'")
                    continue

            # Sanitize name (prevent injection)
            name = self._sanitize_string(raw_name) if raw_name else None

            try:
                async with get_session() as session:
                    company_repo = CompanyRepository(session)
                    company_data = CompanyCreate(
                        name=name,
                        domain=domain,
                        website=website_override or f"https://{domain}",
                        source_file=source_file,
                        source_row=row_num,
                    )
                    company, created = await company_repo.get_or_create(company_data)

                    if not created:
                        logger.debug("Company already exists", domain=domain)
                        skipped += 1
                        continue

                # Enqueue crawl job
                job = CrawlJob(
                    company_id=str(company.id),
                    domain=domain,
                    priority=5,
                    metadata={"import_id": import_id, "source_row": row_num},
                )

                if queue_manager:
                    await queue_manager.enqueue_crawl(job)

                queued += 1
                logger.debug("Queued crawl job", domain=domain, job_id=job.job_id)

            except Exception as exc:
                logger.error("Import row failed", row=row_num, domain=domain, error=str(exc))
                errors.append(f"Row {row_num}: {exc}")
                skipped += 1

        summary = {
            "import_id": import_id,
            "source_file": source_file,
            "total_rows": total,
            "queued_jobs": queued,
            "skipped_rows": skipped,
            "errors": errors[:20],  # cap error list
        }
        logger.info("CSV import complete", **{k: v for k, v in summary.items() if k != "errors"})
        return summary

    def _make_maps_placeholder(self, maps_url: str) -> str:
        """
        Deterministic synthetic domain for an unresolved Google Maps listing,
        so distinct listings don't collide on the `domain` unique constraint
        before their real website is resolved during the crawl phase.
        """
        digest = hashlib.sha1(maps_url.encode("utf-8")).hexdigest()[:16]
        return f"maps-{digest}.pending"

    def _detect_column(self, headers: list[str], aliases: set[str]) -> str | None:
        """Find the first matching column from a set of aliases."""
        for header in headers:
            if header in aliases:
                return header
        return None

    def _sanitize_string(self, value: str) -> str:
        """Basic sanitization: strip dangerous characters."""
        # Remove null bytes, excessive whitespace
        value = value.replace("\x00", "").strip()
        return value[:500]
