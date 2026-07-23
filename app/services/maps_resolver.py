"""
Resolves a Google Maps place-listing link to the business's actual published
website. Google Maps is a directory, not a business's own site — crawling
maps.google.com directly can never yield a business's email. But listings
that have a "Website" button expose the real URL in the page's own DOM
(`a[data-item-id="authority"]`), so we read that directly rather than guess.

If a listing has no website published on Maps, we report that honestly
(returns None) instead of fabricating anything.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.logging import get_logger

logger = get_logger(__name__)

_MAPS_HOSTS = {"goo.gl", "maps.app.goo.gl"}
_MAPS_PENDING_RE = re.compile(r"^maps-[0-9a-f]{16}\.pending$")


def is_maps_url(url: str) -> bool:
    """True if `url` is a Google Maps listing link, not a business's own site."""
    if not url:
        return False
    candidate = url if "://" in url else f"https://{url}"
    parsed = urlparse(candidate)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    if "google." in host and "/maps" in path:
        return True
    return host in _MAPS_HOSTS


def is_pending_maps_domain(domain: str) -> bool:
    """True if `domain` is one of our synthetic placeholders for an
    unresolved Maps listing (see ImportService._make_maps_placeholder)."""
    return bool(domain and _MAPS_PENDING_RE.match(domain))


class MapsResolver:
    """Extracts the real business website from a rendered Google Maps listing."""

    async def resolve(self, maps_url: str, timeout_ms: int = 15000) -> str | None:
        """
        Render `maps_url` and return the business's published website URL,
        or None if the listing has no website (never guessed/fabricated).
        """
        from playwright.async_api import async_playwright

        url = maps_url if "://" in maps_url else f"https://{maps_url}"

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                    try:
                        link = await page.wait_for_selector(
                            'a[data-item-id="authority"]', timeout=timeout_ms
                        )
                    except Exception:
                        return None
                    href = await link.get_attribute("href")
                    return href or None
                finally:
                    await browser.close()
        except Exception as exc:
            logger.warning("Maps resolution failed", url=maps_url, error=str(exc))
            return None
