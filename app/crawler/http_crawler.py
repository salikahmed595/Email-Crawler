"""
HTTP crawler engine using httpx.
Primary strategy — fastest, cheapest, zero overhead.
Uses connection pooling, retry, User-Agent, and rate limiting.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import get_settings
from app.crawler.base_crawler import BaseCrawler, CrawlResponse
from app.logging import get_logger
from app.utils.rate_limiter import get_rate_limiter
from app.utils.url_utils import extract_domain, is_safe_url

logger = get_logger(__name__)

# Shared httpx client (connection pool) — created once per process
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Get or create the shared async HTTP client."""
    global _http_client
    if _http_client is None:
        settings = get_settings()
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout),
            follow_redirects=True,
            max_redirects=10,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
            },
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
            ),
            http2=True,
        )
    return _http_client


async def close_http_client() -> None:
    """Close the shared HTTP client."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


class HttpCrawler(BaseCrawler):
    """
    Static HTTP crawler.
    Priority: first strategy in the adaptive chain.
    """

    @property
    def engine_name(self) -> str:
        return "http"

    async def crawl(self, url: str, **kwargs: Any) -> CrawlResponse:
        """
        Fetch a URL via HTTP. Applies rate limiting per domain.
        Returns CrawlResponse — never raises.
        """
        if not is_safe_url(url):
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error=f"Blocked URL (SSRF prevention): {url}",
            )

        # Rate limit per domain
        try:
            domain = extract_domain(url)
            await get_rate_limiter().acquire(domain)
        except Exception:
            pass  # Rate limiter failure must not block the crawl

        client = get_http_client()
        start = time.monotonic()

        try:
            response = await client.get(url)
            duration_ms = (time.monotonic() - start) * 1000

            # Decode content — handle charset
            try:
                html = response.text
            except Exception:
                html = response.content.decode("utf-8", errors="replace")

            redirect_chain = [str(r.url) for r in response.history]

            logger.debug(
                "HTTP crawl complete",
                url=url,
                status=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            return CrawlResponse(
                url=url,
                final_url=str(response.url),
                html=html,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                engine=self.engine_name,
                success=response.status_code < 400,
                redirect_chain=redirect_chain,
                response_headers=dict(response.headers),
                duration_ms=duration_ms,
            )

        except httpx.TooManyRedirects as exc:
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error=f"Too many redirects: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except httpx.TimeoutException as exc:
            logger.warning("HTTP timeout", url=url, error=str(exc))
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error=f"Timeout: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except httpx.RequestError as exc:
            logger.warning("HTTP request error", url=url, error=str(exc))
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
        except Exception as exc:
            logger.error("Unexpected HTTP error", url=url, error=str(exc))
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
