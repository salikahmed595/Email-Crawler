"""
URL validator — validates and sanitizes URLs before crawling.
Prevents SSRF, directory traversal, and protocol injection.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.logging import get_logger

logger = get_logger(__name__)

_ALLOWED_SCHEMES = {"http", "https"}

# Checked against the whole URL, including the scheme separator.
_BLOCKED_PATTERNS_FULL = [
    re.compile(r"\x00"),            # Null byte injection
    re.compile(r"<script", re.I),   # HTML injection
]

# Checked against the path+query only — matching against the full URL would
# also flag the harmless "://" scheme separator in every valid http(s) URL.
_BLOCKED_PATTERNS_PATH = [
    re.compile(r"\.\./"),           # Directory traversal
    re.compile(r"//[^/]"),          # Protocol-relative host bypass embedded in the path
]

_BLOCKED_HOSTS = frozenset({
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254", "metadata.google.internal",
    "metadata.aws.internal",
})

_PRIVATE_IP_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                         "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                         "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                         "172.30.", "172.31.", "192.168.", "127.")


class UrlValidator:
    """
    Validates URLs before passing them to any crawler engine.
    Rejects unsafe, malformed, or disallowed URLs.
    """

    def validate(self, url: str) -> tuple[bool, str | None]:
        """
        Validate a URL.
        Returns (is_valid, error_reason).
        """
        if not url or not isinstance(url, str):
            return False, "Empty or non-string URL"

        url = url.strip()

        # Length check
        if len(url) > 2048:
            return False, "URL too long"

        # Check for injection patterns anywhere in the URL
        for pattern in _BLOCKED_PATTERNS_FULL:
            if pattern.search(url):
                return False, f"Blocked pattern detected: {pattern.pattern}"

        try:
            parsed = urlparse(url)
        except Exception as exc:
            return False, f"URL parse error: {exc}"

        # Check for injection/bypass patterns in the path+query only —
        # checking the full URL would also match the "://" scheme separator.
        path_and_query = parsed.path + ("?" + parsed.query if parsed.query else "")
        for pattern in _BLOCKED_PATTERNS_PATH:
            if pattern.search(path_and_query):
                return False, f"Blocked pattern detected: {pattern.pattern}"

        # Scheme check
        if parsed.scheme not in _ALLOWED_SCHEMES:
            return False, f"Disallowed scheme: {parsed.scheme!r}"

        # Host check
        host = parsed.hostname or ""
        if not host:
            return False, "Missing hostname"

        if host in _BLOCKED_HOSTS:
            return False, f"Blocked host: {host}"

        # Private IP range check
        for prefix in _PRIVATE_IP_PREFIXES:
            if host.startswith(prefix):
                return False, f"Private IP range blocked: {host}"

        # Basic domain format check
        if "." not in host and not host.startswith("["):  # allow IPv6 brackets
            return False, f"Invalid hostname: {host}"

        return True, None

    def is_valid(self, url: str) -> bool:
        """Convenience method — returns bool only."""
        valid, _ = self.validate(url)
        return valid

    def sanitize(self, url: str) -> str | None:
        """
        Sanitize a URL — returns cleaned URL or None if invalid.
        """
        if not self.is_valid(url):
            return None
        url = url.strip()
        # Remove fragment
        if "#" in url:
            url = url.split("#")[0]
        return url
