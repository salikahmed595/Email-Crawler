"""
Adaptive crawler — orchestrates the fallback chain.

Strategy: always use the cheapest successful engine first.
  1. HTTP Request (static HTML)
  2. Playwright (JS rendering) — only if emails not found
  3. PDF extraction — only if emails still not found
  4. OCR — only if emails still not found

Every stage checks if we already have enough data before escalating.
This keeps resource usage minimal and speed maximal.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.crawler.base_crawler import CrawlResponse
from app.crawler.http_crawler import HttpCrawler
from app.crawler.ocr_crawler import OcrCrawler
from app.crawler.pdf_crawler import PdfCrawler
from app.crawler.playwright_crawler import PlaywrightCrawler
from app.logging import get_logger
from app.parsers.html_parser import HtmlParser
from app.parsers.sitemap_parser import SitemapParser
from app.utils.url_utils import get_base_url, is_contact_page, normalize_url, resolve_url

logger = get_logger(__name__)


@dataclass
class PageResult:
    """Result of crawling a single page."""

    url: str
    response: CrawlResponse
    emails_found: list[str] = field(default_factory=list)
    engine_used: str = "http"


@dataclass
class DomainCrawlResult:
    """Aggregated results from crawling all pages of a domain."""

    domain: str
    base_url: str
    pages: list[PageResult] = field(default_factory=list)
    all_emails: list[dict[str, Any]] = field(default_factory=list)
    engines_used: list[str] = field(default_factory=list)
    total_duration_ms: float = 0.0
    company_metadata: dict[str, Any] = field(default_factory=dict)


class AdaptiveCrawler:
    """
    Orchestrates multi-engine crawling for a single domain.
    Implements the adaptive fallback chain from framework.md.
    """

    def __init__(self) -> None:
        self._http = HttpCrawler()
        self._playwright = PlaywrightCrawler()
        self._pdf = PdfCrawler()
        self._ocr = OcrCrawler()
        self._html_parser = HtmlParser()
        self._sitemap_parser = SitemapParser()
        self._settings = get_settings()

    async def crawl_domain(self, domain: str) -> DomainCrawlResult:
        """
        Crawl a complete domain through the adaptive chain.
        Discovers and visits contact/about/team pages automatically.
        """
        import time

        start = time.monotonic()
        base_url = f"https://{domain}"

        result = DomainCrawlResult(domain=domain, base_url=base_url)

        logger.info("Starting domain crawl", domain=domain)

        # Step 1: Discover pages to crawl (sitemap + known paths)
        pages_to_crawl = await self._discover_pages(base_url)
        logger.debug("Pages to crawl", domain=domain, count=len(pages_to_crawl))

        # Step 2: Crawl each page through the adaptive chain
        crawled_count = 0
        for page_url in pages_to_crawl:
            if crawled_count >= self._settings.max_pages_per_domain:
                logger.debug("Max pages reached", domain=domain, limit=self._settings.max_pages_per_domain)
                break

            page_result = await self._crawl_page_adaptive(page_url)
            result.pages.append(page_result)
            crawled_count += 1

            if page_result.engine_used not in result.engines_used:
                result.engines_used.append(page_result.engine_used)

        result.total_duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "Domain crawl complete",
            domain=domain,
            pages=len(result.pages),
            engines=result.engines_used,
            duration_ms=round(result.total_duration_ms, 2),
        )
        return result

    async def _discover_pages(self, base_url: str) -> list[str]:
        """
        Discover all pages to crawl for a domain.
        Priority: homepage → sitemap → known contact paths.
        """
        pages: list[str] = [base_url]

        # Try to parse sitemap for additional pages
        sitemap_pages = await self._sitemap_parser.discover_pages(base_url)
        for page in sitemap_pages:
            if page not in pages:
                pages.append(page)

        # Add known high-value paths if not already discovered
        known_paths = [
            "/contact",
            "/contact-us",
            "/about",
            "/about-us",
            "/team",
            "/our-team",
            "/staff",
            "/impressum",
            "/imprint",
            "/people",
        ]
        for path in known_paths:
            candidate = base_url.rstrip("/") + path
            if candidate not in pages:
                pages.append(candidate)

        return pages[:self._settings.max_pages_per_domain]

    async def _crawl_page_adaptive(self, url: str) -> PageResult:
        """
        Crawl a single page through the adaptive engine chain.
        Returns as soon as emails are found or all engines are exhausted.
        """
        # --- Stage 1: HTTP (static) ---
        response = await self._http.crawl(url)
        engine_used = "http"

        if response.success and response.html:
            emails = self._html_parser.extract_emails_quick(response.html)
            if emails:
                return PageResult(
                    url=url,
                    response=response,
                    emails_found=emails,
                    engine_used=engine_used,
                )

        # --- Stage 2: Playwright (JS) — only if static failed ---
        # A clean 4xx/5xx from the server (e.g. a guessed /staff path that
        # doesn't exist) is a real, final answer — re-rendering it with a
        # full headless browser wastes 10-20s and won't change the outcome.
        # Only escalate on network-level failures (no status at all) or
        # suspiciously thin/empty responses (likely a JS-rendered shell).
        request_failed = response.status_code is None
        looks_like_js_shell = response.success and (
            not response.html or len(response.html) < 500
        )
        if self._settings.playwright_enabled and (request_failed or looks_like_js_shell):
            logger.debug("Escalating to Playwright", url=url)
            pw_response = await self._playwright.crawl(url)
            if pw_response.success and pw_response.html:
                response = pw_response
                engine_used = "playwright"
                emails = self._html_parser.extract_emails_quick(pw_response.html)
                if emails:
                    return PageResult(
                        url=url,
                        response=response,
                        emails_found=emails,
                        engine_used=engine_used,
                    )

        # No further escalation at page level — PDF/OCR handled separately
        return PageResult(url=url, response=response, engine_used=engine_used)

    async def crawl_pdf(self, url: str) -> CrawlResponse:
        """Crawl a single PDF document."""
        return await self._pdf.crawl(url)

    async def crawl_image_ocr(self, url: str) -> CrawlResponse:
        """Run OCR on a single image."""
        return await self._ocr.crawl(url)

    async def close(self) -> None:
        """Release all crawler resources."""
        await self._playwright.close()
