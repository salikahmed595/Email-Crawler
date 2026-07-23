"""
Domain validator — validates domain format and checks against blocklists.
"""

from __future__ import annotations

import re

from app.logging import get_logger

logger = get_logger(__name__)

# Domains that are obviously not real businesses
_BLOCKED_DOMAINS = frozenset({
    "example.com", "example.org", "example.net",
    "test.com", "test.org", "localhost.com",
    "domain.com", "yourdomain.com", "your-domain.com",
    "website.com", "mywebsite.com", "placeholder.com",
    "invalid.com",
})

_DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)"
    r"+[a-zA-Z]{2,63}$"
)


class DomainValidator:
    """Validates domain names before adding to the crawl queue."""

    def validate(self, domain: str) -> tuple[bool, str | None]:
        """
        Validate a domain string.
        Returns (is_valid, error_reason).
        """
        if not domain or not isinstance(domain, str):
            return False, "Empty domain"

        domain = domain.strip().lower()

        if len(domain) > 253:
            return False, "Domain too long"

        if domain in _BLOCKED_DOMAINS:
            return False, f"Blocked placeholder domain: {domain}"

        if not _DOMAIN_RE.match(domain):
            return False, f"Invalid domain format: {domain}"

        # Must have at least one dot
        if "." not in domain:
            return False, "No TLD in domain"

        # TLD must be at least 2 chars
        tld = domain.rsplit(".", 1)[-1]
        if len(tld) < 2:
            return False, f"Invalid TLD: {tld}"

        return True, None

    def is_valid(self, domain: str) -> bool:
        valid, _ = self.validate(domain)
        return valid

    def normalize(self, raw: str) -> str | None:
        """Normalize a raw domain string. Returns None if invalid."""
        if not raw:
            return None
        domain = raw.strip().lower()
        # Strip protocol
        for prefix in ("https://", "http://", "www."):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        domain = domain.split("/")[0].split("?")[0].split("#")[0].rstrip(".")
        if self.is_valid(domain):
            return domain
        return None
