"""
URL utilities — normalization, domain extraction, SSRF prevention.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

import tldextract

# Protocols that are safe to crawl
ALLOWED_PROTOCOLS = {"http", "https"}

# IPs/ranges to block for SSRF prevention
BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "169.254.169.254",  # AWS metadata
    "metadata.google.internal",
}

_BLOCKED_IP_PREFIXES = ("10.", "172.16.", "192.168.", "127.")


def normalize_url(url: str) -> str:
    """
    Normalize a URL: lowercase scheme+host, remove trailing slash,
    ensure scheme is present.
    """
    url = url.strip()
    if not url:
        raise ValueError("Empty URL")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            parsed.params,
            parsed.query,
            "",  # strip fragment
        )
    )
    return normalized


def extract_domain(url: str) -> str:
    """Extract the registered domain from a URL (e.g. 'example.com')."""
    extracted = tldextract.extract(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    raise ValueError(f"Cannot extract domain from: {url}")


def is_safe_url(url: str) -> bool:
    """
    Return True if the URL is safe to crawl.
    Prevents SSRF by blocking internal/private addresses and non-HTTP protocols.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_PROTOCOLS:
            return False
        host = parsed.hostname or ""
        if not host:
            return False
        if host in BLOCKED_HOSTS:
            return False
        for prefix in _BLOCKED_IP_PREFIXES:
            if host.startswith(prefix):
                return False
        return True
    except Exception:
        return False


def resolve_url(base_url: str, href: str) -> str | None:
    """
    Resolve a potentially relative href against a base URL.
    Returns None if the result is not a safe HTTP/HTTPS URL.
    """
    try:
        resolved = urljoin(base_url, href.strip())
        if is_safe_url(resolved):
            return resolved
    except Exception:
        pass
    return None


def get_base_url(url: str) -> str:
    """Return the scheme + host (e.g. 'https://example.com')."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def is_contact_page(url: str) -> bool:
    """Heuristic: does this URL look like a contact/about/team page?"""
    patterns = [
        r"/contact",
        r"/about",
        r"/team",
        r"/staff",
        r"/people",
        r"/get-in-touch",
        r"/reach-us",
        r"/our-team",
        r"/meet-the-team",
        r"/impressum",
        r"/imprint",
    ]
    lower = url.lower()
    return any(re.search(p, lower) for p in patterns)


def clean_domain(raw: str) -> str:
    """
    Clean a raw domain or URL string to a bare domain.
    e.g. 'https://www.example.com/path' → 'example.com'
    """
    raw = raw.strip().lower()
    for prefix in ("https://", "http://", "www."):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    raw = raw.split("/")[0].split("?")[0].split("#")[0]
    return raw
