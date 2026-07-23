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

from sqlalchemy.exc import IntegrityError

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
from app.services.maps_resolver import MapsResolver, is_pending_maps_domain
from app.services.summary_service import SummaryService
from app.storage.database import get_session
from app.storage.repositories.company_repo import CompanyRepository
from app.storage.repositories.email_repo import EmailRepository
from app.validators.domain_validator import DomainValidator
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
        self._maps_resolver = MapsResolver()
        self._domain_validator = DomainValidator()

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
            # ---- Step 0: Resolve Google Maps listings to a real website ----
            # A Maps listing link is a directory page, not the business's own
            # site — it can never contain the business's email. If this row
            # came from a Maps export, read the business's actual published
            # website off the listing itself (never guessed) before crawling.
            if is_pending_maps_domain(domain):
                resolved_domain, skip_reason = await self._resolve_maps_listing(company_id)
                if resolved_domain is None:
                    # No crawlable site: either the listing has no published
                    # website, or another row already resolved to the same
                    # one. Both are honest results, not crawl failures.
                    return await self._finish_maps_skip(company_id, start, skip_reason)
                domain = resolved_domain

            # ---- Step 1: Crawl ----
            crawl_result = await self._adaptive_crawler.crawl_domain(domain)

            # ---- Step 2-4: Extract + Validate + Store ----
            all_emails: list[EmailCreate] = []
            company_metadata: dict[str, Any] = {}
            engines_used: list[str] = []
            dedup = DedupService()
            homepage_response = None
            homepage_parsed = None
            crawl_records: list[CrawlResult] = []

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

                # Extract company metadata from the first successful page.
                # Extractor already falls back through Schema.org -> OpenGraph
                # -> HTML meta description, so this must run even when the
                # page has no Schema.org markup (most small business sites).
                if not company_metadata:
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

                # Collect crawl result (stored in one batched transaction
                # after the loop — one write transaction per company, not
                # one per page, to avoid "database is locked" contention
                # when several crawling agents write concurrently).
                crawl_records.append(
                    CrawlResult(
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
                )

            if crawl_records:
                async with get_session() as session:
                    session.add_all(crawl_records)

            # ---- Step 4b: Detect website issues (deterministic) ----
            detected_issues = self._issue_detector.detect(
                homepage_response, homepage_parsed, crawl_result.pages
            )
            issue_summary = self._issue_detector.summarize(detected_issues)
            company_name_hint = company_metadata.get("name") if company_metadata else None
            if use_ai_summary:
                issue_summary = await self._summary_service.polish(
                    company_name_hint, detected_issues, issue_summary
                )

            # ---- Step 4c: Business summary (what they do), from real
            # crawled facts only — never invented ----
            business_summary = self._summary_service.deterministic_business_summary(
                company_metadata
            )
            if use_ai_summary:
                business_summary = await self._summary_service.business_summary(
                    company_name_hint, business_summary
                )
            address = (company_metadata or {}).get("address") or {}
            state = address.get("state") if isinstance(address, dict) else None

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
                    "business_summary": business_summary,
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
                "name": company_name_hint,
                "pages_crawled": len(crawl_result.pages),
                "emails_stored": stored_count,
                "emails": sorted({e.address for e in all_emails}),
                "engines_used": engines_used,
                "duration_ms": round(duration_ms, 2),
                "status": "completed",
                "website_issues": [text for _, text in detected_issues],
                "issue_summary": issue_summary,
                "business_summary": business_summary,
                "state": state,
            }
            logger.info(
                "Company completed",
                **{k: v for k, v in summary.items() if k not in ("business_summary", "emails")},
            )
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

    async def _resolve_maps_listing(
        self, company_id: uuid.UUID
    ) -> tuple[str | None, str | None]:
        """
        Resolve a pending Google Maps placeholder to the business's real
        website, updating the company's domain/website in place.

        Returns (resolved_domain, skip_reason). skip_reason is only set when
        resolved_domain is None, and is one of "no_website" (the listing has
        nothing published) or "duplicate_listing" (another row in this batch
        already resolved to the same real site).
        """
        async with get_session() as session:
            company = await CompanyRepository(session).get_by_id(company_id)
        maps_url = company.website if company else None
        if not maps_url:
            return None, "no_website"

        resolved_url = await self._maps_resolver.resolve(maps_url)
        if not resolved_url:
            return None, "no_website"

        resolved_domain = self._domain_validator.normalize(resolved_url)
        if not resolved_domain:
            return None, "no_website"

        try:
            async with get_session() as session:
                company_repo = CompanyRepository(session)
                existing = await company_repo.get_by_domain(resolved_domain)
                if existing and existing.id != company_id:
                    return None, "duplicate_listing"
                await company_repo.update_metadata(
                    company_id, {"domain": resolved_domain, "website": resolved_url}
                )
        except IntegrityError:
            # Lost a race with a concurrent worker resolving to the same site.
            return None, "duplicate_listing"

        return resolved_domain, None

    async def _finish_maps_skip(
        self, company_id: uuid.UUID, start: float, reason: str | None
    ) -> dict[str, Any]:
        """Finalize a Maps-sourced company that has no site to crawl."""
        issue_summary = (
            "No website listed on Google Maps"
            if reason == "no_website"
            else "Same website as another listing in this batch"
        )
        business_summary = "No business description found on site."
        async with get_session() as session:
            company_repo = CompanyRepository(session)
            await company_repo.update_metadata(
                company_id,
                {
                    "status": "completed",
                    "website_issues": [issue_summary],
                    "issue_summary": issue_summary,
                    "business_summary": business_summary,
                },
            )
        duration_ms = (time.monotonic() - start) * 1000
        summary = {
            "company_id": str(company_id),
            "domain": None,
            "name": None,
            "pages_crawled": 0,
            "emails_stored": 0,
            "emails": [],
            "engines_used": [],
            "duration_ms": round(duration_ms, 2),
            "status": "completed",
            "website_issues": [issue_summary],
            "issue_summary": issue_summary,
            "business_summary": business_summary,
            "state": None,
        }
        logger.info("Company skipped (Maps listing)", reason=reason, **{
            k: v for k, v in summary.items() if k not in ("website_issues", "issue_summary")
        })
        return summary

    async def close(self) -> None:
        """Release crawler resources."""
        await self._adaptive_crawler.close()
