"""
Crawl service — orchestrates the full pipeline for a single company domain.
Business logic lives here, not in workers or API routes.

Pipeline:
  1. Crawl all pages (adaptive engine)
  2. Parse HTML
  3. Extract emails, phones, social, technologies, company metadata
  4. Validate all emails (10-stage)
  5. Calculate confidence (confidence engine)
  6. Deduplicate
  7. Store to database
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.crawler.adaptive_crawler import AdaptiveCrawler
from app.extractors.company_extractor import CompanyExtractor
from app.extractors.email_extractor import EmailExtractor
from app.extractors.phone_extractor import PhoneExtractor
from app.extractors.social_extractor import SocialExtractor
from app.extractors.technology_extractor import TechnologyExtractor
from app.logging import get_logger
from app.models.crawl_result import CrawlResult
from app.parsers.html_parser import HtmlParser
from app.schemas.email_schema import EmailCreate
from app.services.confidence_engine import ConfidenceEngine
from app.services.dedup_service import DedupService
from app.services.issue_detector import IssueDetector
from app.services.summary_service import SummaryService
from app.storage.database import get_session
from app.storage.repositories.company_repo import CompanyRepository
from app.storage.repositories.email_repo import EmailRepository
from app.validators.email_validator import EmailValidator

logger = get_logger(__name__)


class CrawlService:
    """
    Orchestrates the complete crawl pipeline for one company.
    Stateless — all state goes to database.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._html_parser = HtmlParser()
        self._email_extractor = EmailExtractor()
        self._phone_extractor = PhoneExtractor()
        self._social_extractor = SocialExtractor()
        self._tech_extractor = TechnologyExtractor()
        self._company_extractor = CompanyExtractor()
        self._email_validator = EmailValidator()
        self._confidence_engine = ConfidenceEngine()
        self._adaptive_crawler = AdaptiveCrawler()
        self._issue_detector = IssueDetector()
        self._summary_service = SummaryService()

    async def process_company(
        self,
        company_id: uuid.UUID,
        domain: str,
        use_ai_summary: bool = False,
    ) -> dict[str, Any]:
        """
        Run the full pipeline for a company.
        Returns a summary dict.
        """
        start = time.monotonic()
        logger.info("Processing company", company_id=str(company_id), domain=domain)

        async with get_session() as session:
            company_repo = CompanyRepository(session)
            email_repo = EmailRepository(session)

            # Mark as crawling
            await company_repo.update_status(company_id, "crawling")

        try:
            # ---- Step 1: Crawl ----
            crawl_result = await self._adaptive_crawler.crawl_domain(domain)

            # ---- Step 2-4: Extract + Validate + Store ----
            all_emails: list[EmailCreate] = []
            company_metadata: dict[str, Any] = {}
            engines_used: list[str] = []
            dedup = DedupService()
            homepage_response = None
            homepage_parsed = None

            for page in crawl_result.pages:
                if homepage_response is None and page.url == crawl_result.base_url:
                    homepage_response = page.response

                if not page.response.success or not page.response.html:
                    continue

                html = page.response.html
                page_url = page.response.final_url or page.url

                # Parse
                parsed = self._html_parser.parse(html, base_url=page_url)

                # Track the homepage's parsed content for issue detection
                if homepage_parsed is None and page.url == crawl_result.base_url:
                    homepage_parsed = parsed

                # Extract emails
                extracted_emails = self._email_extractor.extract_from_parsed(
                    parsed, page_url
                )
                # Also run raw HTML strategies (JS, comments, base64, Cloudflare)
                raw_emails = self._email_extractor.extract_from_raw_html(html, page_url)
                extracted_emails.extend(raw_emails)

                # Validate and store each email
                for extracted in extracted_emails:
                    is_dup, addr_hash = dedup.check_and_mark(extracted.address)
                    if is_dup:
                        continue

                    validation = await self._email_validator.validate(extracted.address)

                    # Calculate confidence
                    signals = self._confidence_engine.build_signals_from_extraction(
                        extraction_method=extracted.method,
                        validation_result=validation,
                        domain=domain,
                        email_address=extracted.address,
                        page_url=page_url,
                    )
                    confidence = self._confidence_engine.calculate(signals)

                    if confidence < self._settings.min_email_confidence:
                        logger.debug(
                            "Email below confidence threshold",
                            address=extracted.address,
                            confidence=confidence,
                        )
                        continue

                    all_emails.append(
                        EmailCreate(
                            company_id=company_id,
                            address=extracted.address,
                            address_hash=addr_hash,
                            source=extracted.source,
                            method=extracted.method,
                            page=extracted.page,
                            confidence=confidence,
                            discovered_at=extracted.timestamp or datetime.now(timezone.utc),
                            is_valid_syntax=validation.is_valid_syntax,
                            is_valid_domain=validation.is_valid_domain,
                            mx_valid=validation.mx_valid,
                            smtp_valid=validation.smtp_valid,
                            is_disposable=validation.is_disposable,
                            is_role_based=validation.is_role_based,
                            is_duplicate=False,
                            validation_status=validation.validation_status,
                            notes="; ".join(validation.notes) if validation.notes else None,
                        )
                    )

                # Extract company metadata from first successful page
                if not company_metadata and parsed.schema_org:
                    company_metadata = self._company_extractor.extract(parsed, domain)

                # Extract phone numbers
                phones = self._phone_extractor.extract(parsed.text_content, page_url)
                if phones:
                    company_metadata.setdefault("phone_numbers", [])
                    existing_phones = set(company_metadata["phone_numbers"])
                    for phone in phones:
                        if phone.value not in existing_phones:
                            company_metadata["phone_numbers"].append(phone.value)
                            existing_phones.add(phone.value)

                # Extract social links
                social_links = self._social_extractor.extract(html, page_url)
                if social_links:
                    company_metadata.setdefault("social_links", {})
                    for platform, url in social_links.items():
                        company_metadata["social_links"].setdefault(platform, url)

                # Extract technologies
                tech = self._tech_extractor.extract(
                    html, dict(page.response.response_headers)
                )
                if tech:
                    company_metadata.setdefault("technologies", [])
                    existing_names = {t["name"] for t in company_metadata["technologies"]}
                    for t in tech:
                        if t["name"] not in existing_names:
                            company_metadata["technologies"].append(t)
                            existing_names.add(t["name"])

                # Track engines used
                if page.engine_used not in engines_used:
                    engines_used.append(page.engine_used)

                # Store crawl result
                async with get_session() as session:
                    crawl_rec = CrawlResult(
                        company_id=company_id,
                        url=page.url,
                        final_url=page.response.final_url,
                        engine_used=page.response.engine,
                        status_code=page.response.status_code,
                        content_type=page.response.content_type,
                        crawl_duration_ms=page.response.duration_ms,
                        crawled_at=datetime.now(timezone.utc),
                        success=page.response.success,
                        error_message=page.response.error,
                        emails_found=len(extracted_emails),
                        response_headers=dict(page.response.response_headers),
                        redirect_chain=page.response.redirect_chain,
                        tech_stack=tech if tech else None,
                    )
                    session.add(crawl_rec)

            # ---- Step 4b: Detect website issues (deterministic) ----
            detected_issues = self._issue_detector.detect(
                homepage_response, homepage_parsed, crawl_result.pages
            )
            issue_summary = self._issue_detector.summarize(detected_issues)
            if use_ai_summary:
                company_name_hint = company_metadata.get("name") if company_metadata else None
                issue_summary = await self._summary_service.polish(
                    company_name_hint, detected_issues, issue_summary
                )

            # ---- Step 5: Store emails ----
            async with get_session() as session:
                email_repo = EmailRepository(session)
                stored_count = 0
                for email_data in all_emails:
                    _, created = await email_repo.create_or_skip(email_data)
                    if created:
                        stored_count += 1

            # ---- Step 6: Update company metadata + status ----
            async with get_session() as session:
                company_repo = CompanyRepository(session)
                update_data: dict[str, Any] = {
                    "status": "completed",
                    "website_issues": [text for _, text in detected_issues],
                    "issue_summary": issue_summary,
                }
                if company_metadata:
                    for field in [
                        "name", "description", "address", "phone_numbers",
                        "social_links", "technologies", "services",
                        "opening_hours", "team_members", "industry", "category",
                    ]:
                        if field in company_metadata and company_metadata[field]:
                            update_data[field] = company_metadata[field]
                await company_repo.update_metadata(company_id, update_data)

            duration_ms = (time.monotonic() - start) * 1000
            summary = {
                "company_id": str(company_id),
                "domain": domain,
                "pages_crawled": len(crawl_result.pages),
                "emails_stored": stored_count,
                "engines_used": engines_used,
                "duration_ms": round(duration_ms, 2),
                "status": "completed",
                "website_issues": [text for _, text in detected_issues],
                "issue_summary": issue_summary,
            }
            logger.info("Company completed", **summary)
            return summary

        except Exception as exc:
            logger.error(
                "Company crawl failed",
                company_id=str(company_id),
                domain=domain,
                error=str(exc),
            )
            async with get_session() as session:
                company_repo = CompanyRepository(session)
                await company_repo.update_status(
                    company_id, "failed", error_message=str(exc)
                )
            raise

    async def close(self) -> None:
        """Release crawler resources."""
        await self._adaptive_crawler.close()
