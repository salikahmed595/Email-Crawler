"""
Sitemap parser — discovers pages from sitemap.xml and robots.txt.
Finds contact/about/team pages to prioritize for email discovery.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from app.logging import get_logger
from app.utils.url_utils import is_contact_page, is_safe_url

logger = get_logger(__name__)

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SitemapParser:
    """
    Discovers crawlable pages from XML sitemaps and robots.txt.
    Prioritizes contact-relevant pages.
    """

    async def discover_pages(self, base_url: str, max_pages: int = 50) -> list[str]:
        """
        Discover pages from sitemap.xml / robots.txt.
        Returns a prioritized list — contact pages first.
        """
        pages: list[str] = []

        # Try common sitemap locations
        sitemap_urls = [
            base_url.rstrip("/") + "/sitemap.xml",
            base_url.rstrip("/") + "/sitemap_index.xml",
            base_url.rstrip("/") + "/sitemap.xml.gz",
        ]

        # Also check robots.txt for sitemap location
        robots_sitemap = await self._get_sitemap_from_robots(base_url)
        if robots_sitemap:
            sitemap_urls.insert(0, robots_sitemap)

        for sitemap_url in sitemap_urls:
            discovered = await self._parse_sitemap(sitemap_url, max_pages)
            if discovered:
                pages.extend(discovered)
                break

        # Deduplicate and prioritize contact pages
        seen: set[str] = set()
        contact_pages: list[str] = []
        other_pages: list[str] = []

        for page in pages:
            if page not in seen and is_safe_url(page):
                seen.add(page)
                if is_contact_page(page):
                    contact_pages.append(page)
                else:
                    other_pages.append(page)

        return (contact_pages + other_pages)[:max_pages]

    async def _get_sitemap_from_robots(self, base_url: str) -> str | None:
        """Extract sitemap URL from robots.txt."""
        try:
            import httpx

            robots_url = base_url.rstrip("/") + "/robots.txt"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(robots_url)
            if response.status_code == 200:
                for line in response.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        url = line.split(":", 1)[1].strip()
                        if url.startswith("http"):
                            return url
        except Exception:
            pass
        return None

    async def _parse_sitemap(self, sitemap_url: str, max_pages: int) -> list[str]:
        """Download and parse a sitemap XML file."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(sitemap_url)

            if response.status_code != 200:
                return []

            content = response.text
            return self._extract_urls_from_xml(content, max_pages)

        except Exception as exc:
            logger.debug("Sitemap parse failed", url=sitemap_url, error=str(exc))
            return []

    def _extract_urls_from_xml(self, xml_content: str, max_pages: int) -> list[str]:
        """Extract <loc> URLs from sitemap XML."""
        urls: list[str] = []
        try:
            root = ET.fromstring(xml_content)
            # Handle namespace-prefixed and unprefixed loc tags
            for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                url = (loc.text or "").strip()
                if url and is_safe_url(url):
                    urls.append(url)
                    if len(urls) >= max_pages:
                        break
            # Fallback: no namespace
            if not urls:
                for loc in root.iter("loc"):
                    url = (loc.text or "").strip()
                    if url and is_safe_url(url):
                        urls.append(url)
                        if len(urls) >= max_pages:
                            break
        except ET.ParseError as exc:
            logger.debug("Sitemap XML parse error", error=str(exc))
        return urls
