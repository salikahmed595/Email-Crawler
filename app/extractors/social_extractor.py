"""
Social link extractor — finds LinkedIn, Twitter/X, Facebook, Instagram, YouTube links.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.logging import get_logger
from app.schemas.email_schema import ExtractedValue

logger = get_logger(__name__)

_SOCIAL_PATTERNS: dict[str, re.Pattern] = {
    "linkedin": re.compile(
        r"https?://(?:www\.)?linkedin\.com/(?:company|in|profile)/[a-zA-Z0-9\-_/]+",
        re.IGNORECASE,
    ),
    "twitter": re.compile(
        r"https?://(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+",
        re.IGNORECASE,
    ),
    "facebook": re.compile(
        r"https?://(?:www\.)?facebook\.com/[a-zA-Z0-9.\-_/]+",
        re.IGNORECASE,
    ),
    "instagram": re.compile(
        r"https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._]+",
        re.IGNORECASE,
    ),
    "youtube": re.compile(
        r"https?://(?:www\.)?youtube\.com/(?:channel|c|user)/[a-zA-Z0-9\-_]+",
        re.IGNORECASE,
    ),
    "github": re.compile(
        r"https?://(?:www\.)?github\.com/[a-zA-Z0-9\-]+",
        re.IGNORECASE,
    ),
}


class SocialExtractor:
    """Extracts social media profile links from HTML/text."""

    def extract(self, html: str, source_url: str) -> dict[str, str]:
        """
        Extract social links from HTML.
        Returns dict mapping platform → URL.
        """
        found: dict[str, str] = {}

        for platform, pattern in _SOCIAL_PATTERNS.items():
            match = pattern.search(html)
            if match:
                url = match.group(0)
                # Clean trailing slashes and query params
                url = url.rstrip("/").split("?")[0]
                found[platform] = url

        return found
