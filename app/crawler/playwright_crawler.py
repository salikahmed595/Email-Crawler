"""
Playwright crawler engine — JavaScript rendering fallback.
Used ONLY when static HTTP fails to yield emails.
Reuses browser context across pages (no new browser per site).
"""

from __future__ import annotations

import time
from typing import Any

from app.config import get_settings
from app.crawler.base_crawler import BaseCrawler, CrawlResponse
from app.logging import get_logger

logger = get_logger(__name__)

# Shared Playwright browser instance (reused across calls)
_playwright_instance: Any = None
_browser_instance: Any = None
_browser_context: Any = None


async def get_browser_context() -> Any:
    """
    Get or create the shared Playwright browser context.
    Reusing context across pages avoids browser startup overhead.
    """
    global _playwright_instance, _browser_instance, _browser_context

    if _browser_context is not None:
        return _browser_context

    from playwright.async_api import async_playwright

    settings = get_settings()
    _playwright_instance = await async_playwright().start()

    browser_type = getattr(_playwright_instance, settings.playwright_browser)
    _browser_instance = await browser_type.launch(
        headless=settings.playwright_headless,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    _browser_context = await _browser_instance.new_context(
        user_agent=settings.user_agent,
        java_script_enabled=True,
        ignore_https_errors=True,
        viewport={"width": 1280, "height": 800},
    )
    logger.info("Playwright browser context initialized")
    return _browser_context


async def close_playwright() -> None:
    """Close the Playwright browser and release resources."""
    global _playwright_instance, _browser_instance, _browser_context
    if _browser_context:
        await _browser_context.close()
        _browser_context = None
    if _browser_instance:
        await _browser_instance.close()
        _browser_instance = None
    if _playwright_instance:
        await _playwright_instance.stop()
        _playwright_instance = None


class PlaywrightCrawler(BaseCrawler):
    """
    Playwright-based JS rendering crawler.
    Fallback strategy — only used when static crawling is insufficient.
    """

    @property
    def engine_name(self) -> str:
        return "playwright"

    async def crawl(self, url: str, **kwargs: Any) -> CrawlResponse:
        """
        Load a URL with full JS execution. Returns rendered HTML.
        Never raises — returns CrawlResponse with success=False on error.
        """
        settings = get_settings()
        if not settings.playwright_enabled:
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error="Playwright disabled by configuration",
            )

        start = time.monotonic()
        page = None

        try:
            context = await get_browser_context()
            page = await context.new_page()

            # Block unnecessary resources to speed up page load
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,eot}",
                lambda route: route.abort(),
            )

            response = await page.goto(
                url,
                timeout=settings.playwright_timeout,
                wait_until="networkidle",
            )

            # Wait for dynamic content
            await page.wait_for_timeout(2000)

            html = await page.content()
            final_url = page.url
            status_code = response.status if response else None
            duration_ms = (time.monotonic() - start) * 1000

            logger.debug(
                "Playwright crawl complete",
                url=url,
                final_url=final_url,
                status=status_code,
                duration_ms=round(duration_ms, 2),
            )

            return CrawlResponse(
                url=url,
                final_url=final_url,
                html=html,
                status_code=status_code,
                content_type="text/html",
                engine=self.engine_name,
                success=True,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            logger.warning("Playwright crawl failed", url=url, error=str(exc))
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def close(self) -> None:
        """Close the shared Playwright browser."""
        await close_playwright()
