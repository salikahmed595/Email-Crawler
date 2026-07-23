"""
HTML parser — extracts structured data from HTML using BeautifulSoup4 + lxml.
Handles: DOM structure, links, metadata, Schema.org, JSON-LD, OpenGraph, Microdata.
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.logging import get_logger

logger = get_logger(__name__)

# Quick email regex for scanning (full validation done in validator)
_EMAIL_RE = re.compile(
    r"""(?:[a-zA-Z0-9!#$%&'*+=?^_`{|}~-]+
        (?:\.[a-zA-Z0-9!#$%&'*+=?^_`{|}~-]+)*
        |"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]
          |\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")
        @
        (?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+
           [a-zA-Z]{2,})""",
    re.VERBOSE | re.IGNORECASE,
)


class ParsedPage:
    """Structured result from parsing an HTML page."""

    def __init__(self) -> None:
        self.title: str = ""
        self.description: str = ""
        self.links: list[str] = []
        self.mailto_links: list[str] = []
        self.emails_raw: list[str] = []
        self.phones: list[str] = []
        self.schema_org: list[dict] = []
        self.json_ld: list[dict] = []
        self.open_graph: dict[str, str] = {}
        self.microdata: list[dict] = []
        self.meta: dict[str, str] = {}
        self.pdf_links: list[str] = []
        self.image_links: list[str] = []
        self.text_content: str = ""
        self.footer_text: str = ""
        self.header_text: str = ""


class HtmlParser:
    """
    Comprehensive HTML parser.
    Extracts all 13 data collection layers defined in framework.md.
    """

    def parse(self, html: str, base_url: str = "") -> ParsedPage:
        """
        Parse HTML and extract all structured data.
        Returns a ParsedPage with all fields populated.
        """
        result = ParsedPage()
        if not html or not html.strip():
            return result

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            try:
                soup = BeautifulSoup(html, "html.parser")
            except Exception as exc:
                logger.warning("HTML parse failed", error=str(exc))
                return result

        # Layer 1: Basic metadata
        self._parse_title(soup, result)
        self._parse_meta(soup, result)

        # Layer 2: Links and mailto
        self._parse_links(soup, result, base_url)

        # Layer 3: OpenGraph
        self._parse_opengraph(soup, result)

        # Layer 4: Schema.org + JSON-LD
        self._parse_json_ld(soup, result)

        # Layer 5: Microdata
        self._parse_microdata(soup, result)

        # Layer 6: Text content (emails in plain text)
        self._parse_text(soup, result)

        # Layer 7: Footer and header
        self._parse_sections(soup, result)

        return result

    def extract_emails_quick(self, html: str) -> list[str]:
        """
        Fast email extraction from raw HTML — no full parse.
        Used by adaptive crawler to quickly check if a page has emails.
        """
        return list(set(_EMAIL_RE.findall(html)))

    # -------------------------------------------------------------------------
    # Private parsers
    # -------------------------------------------------------------------------

    def _parse_title(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        title_tag = soup.find("title")
        if title_tag:
            result.title = title_tag.get_text(strip=True)[:500]

    def _parse_meta(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            prop = meta.get("property", "").lower()
            content = meta.get("content", "")
            key = name or prop
            if key and content:
                result.meta[key] = content[:1000]
        result.description = result.meta.get("description", "")[:500]

    def _parse_links(
        self, soup: BeautifulSoup, result: ParsedPage, base_url: str
    ) -> None:
        from app.utils.url_utils import resolve_url

        for anchor in soup.find_all("a", href=True):
            href = str(anchor["href"]).strip()

            # mailto links
            if href.lower().startswith("mailto:"):
                email = href[7:].split("?")[0].strip()
                if email and "@" in email:
                    result.mailto_links.append(email.lower())
                    result.emails_raw.append(email.lower())
                continue

            # PDF links
            if href.lower().endswith(".pdf"):
                if base_url:
                    resolved = resolve_url(base_url, href)
                    if resolved:
                        result.pdf_links.append(resolved)
                continue

            # Regular links
            if base_url:
                resolved = resolve_url(base_url, href)
                if resolved:
                    result.links.append(resolved)

        # Image links
        for img in soup.find_all("img", src=True):
            src = str(img["src"]).strip()
            if base_url and src:
                from app.utils.url_utils import resolve_url
                resolved = resolve_url(base_url, src)
                if resolved:
                    result.image_links.append(resolved)

    def _parse_opengraph(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        for meta in soup.find_all("meta", property=re.compile(r"^og:", re.I)):
            prop = meta.get("property", "").replace("og:", "")
            content = meta.get("content", "")
            if prop and content:
                result.open_graph[prop] = content[:500]

    def _parse_json_ld(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    result.json_ld.append(data)
                    if data.get("@type"):
                        result.schema_org.append(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            result.json_ld.append(item)
                            if item.get("@type"):
                                result.schema_org.append(item)
            except (json.JSONDecodeError, AttributeError):
                continue

    def _parse_microdata(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        for elem in soup.find_all(attrs={"itemtype": True}):
            item_type = str(elem.get("itemtype", ""))
            props: dict[str, Any] = {"@type": item_type, "properties": {}}
            for prop_elem in elem.find_all(attrs={"itemprop": True}):
                prop_name = str(prop_elem.get("itemprop", ""))
                value = (
                    prop_elem.get("content")
                    or prop_elem.get("href")
                    or prop_elem.get_text(strip=True)
                )
                if prop_name and value:
                    props["properties"][prop_name] = value
            result.microdata.append(props)

    def _parse_text(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        # Remove script and style tags
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        result.text_content = text[:50000]  # cap to prevent memory issues

        # Extract emails from visible text
        found = _EMAIL_RE.findall(text)
        for email in found:
            # The permissive local-part character class can greedily swallow
            # a leading quote/bracket from surrounding text — strip it back off.
            normalized = email.strip().strip("'\"`()[]<>,;").lower()
            if normalized not in result.emails_raw:
                result.emails_raw.append(normalized)

    def _parse_sections(self, soup: BeautifulSoup, result: ParsedPage) -> None:
        # Footer
        footer = soup.find("footer") or soup.find(class_=re.compile(r"footer", re.I))
        if footer and isinstance(footer, Tag):
            result.footer_text = footer.get_text(separator=" ", strip=True)[:5000]

        # Header
        header = soup.find("header") or soup.find(class_=re.compile(r"header", re.I))
        if header and isinstance(header, Tag):
            result.header_text = header.get_text(separator=" ", strip=True)[:2000]
