"""
RSS feed parser — extracts company metadata from RSS/Atom feeds.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)


class RssParser:
    """Parses RSS/Atom feeds for company metadata."""

    async def parse_feed(self, feed_url: str) -> dict[str, Any]:
        """
        Download and parse an RSS/Atom feed.
        Returns extracted metadata.
        """
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(feed_url)

            if response.status_code != 200:
                return {}

            return self._parse_xml(response.text)

        except Exception as exc:
            logger.debug("RSS parse failed", url=feed_url, error=str(exc))
            return {}

    def _parse_xml(self, xml_content: str) -> dict[str, Any]:
        """Extract metadata from RSS/Atom XML."""
        result: dict[str, Any] = {}
        try:
            root = ET.fromstring(xml_content)

            # RSS 2.0
            channel = root.find("channel")
            if channel is not None:
                title = channel.find("title")
                if title is not None and title.text:
                    result["title"] = title.text.strip()

                desc = channel.find("description")
                if desc is not None and desc.text:
                    result["description"] = desc.text.strip()

                link = channel.find("link")
                if link is not None and link.text:
                    result["link"] = link.text.strip()

            # Atom
            atom_ns = "http://www.w3.org/2005/Atom"
            title = root.find(f"{{{atom_ns}}}title")
            if title is not None and title.text:
                result["title"] = title.text.strip()

        except ET.ParseError:
            pass

        return result

    async def discover_feed_url(self, base_url: str) -> str | None:
        """Try to find a feed URL for a website."""
        try:
            import httpx
            from bs4 import BeautifulSoup

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(base_url)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("link", rel=re.compile(r"alternate", re.I)):
                link_type = str(link.get("type", ""))
                if "rss" in link_type or "atom" in link_type:
                    href = link.get("href", "")
                    if href:
                        from app.utils.url_utils import resolve_url
                        return resolve_url(base_url, str(href))
        except Exception:
            pass
        return None
