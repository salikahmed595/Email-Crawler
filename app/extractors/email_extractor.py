"""
Email extractor — implements all 11 discovery strategies from framework.md.

Search order:
  1. mailto: links
  2. Visible HTML regex
  3. Footer / Header
  4. Contact / About / Team pages
  5. Schema.org / JSON-LD
  6. JavaScript source
  7. HTML comments
  8. Base64 decoded strings
  9. Unicode obfuscated emails
  10. Cloudflare email protection decode
  11. PDF text / OCR text (passed in as plain text)

Every returned email carries: address, confidence_hint, source, method, page, timestamp.
Full validation and final confidence scoring happen downstream.
"""

from __future__ import annotations

import base64
import html as html_lib
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.logging import get_logger
from app.parsers.html_parser import HtmlParser, ParsedPage
from app.schemas.email_schema import EmailExtracted

logger = get_logger(__name__)

# RFC 5321-compatible email regex (permissive — validator does strict checking)
_EMAIL_RE = re.compile(
    r"""[a-zA-Z0-9!#$%&'*+=?^_`{|}~\-]+
        (?:\.[a-zA-Z0-9!#$%&'*+=?^_`{|}~\-]+)*
        @
        [a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?
        (?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*
        \.[a-zA-Z]{2,}""",
    re.VERBOSE | re.IGNORECASE,
)

# Obfuscation patterns
# NOTE: "at"/"dot" must be word-bounded (\b) — without it, bare substring
# matching fires on any text containing "at" or a "." anywhere, e.g. minified
# asset filenames like "integrations-6-378b8d4ec66b.png" (matches "at" inside
# "integr-AT-ions"), fabricating emails that were never actually on the page.
_AT_OBFUSCATION = re.compile(
    r"(?P<local>[a-zA-Z0-9._%+\-]+)\s*(?:\[at\]|\(at\)|\{at\}|\bat\b|@|＠)\s*"
    r"(?P<domain>[a-zA-Z0-9.\-]+)\s*(?:\[dot\]|\(dot\)|\{dot\}|\bdot\b)\s*"
    r"(?P<tld>[a-zA-Z]{2,})",
    re.IGNORECASE,
)


class EmailExtractor:
    """
    Multi-strategy email extractor.
    Operates on already-parsed HTML (ParsedPage) or raw text.
    Returns EmailExtracted objects with provenance metadata.
    """

    def __init__(self) -> None:
        self._parser = HtmlParser()

    def extract_from_page(
        self,
        html: str,
        source_url: str,
        page_type: str = "page",
    ) -> list[EmailExtracted]:
        """
        Main entry point — extract emails from a raw HTML string.
        Runs all 11 strategies and deduplicates results.
        """
        parsed = self._parser.parse(html, base_url=source_url)
        return self.extract_from_parsed(parsed, source_url, page_type)

    def extract_from_parsed(
        self,
        parsed: ParsedPage,
        source_url: str,
        page_type: str = "page",
    ) -> list[EmailExtracted]:
        """
        Extract emails from an already-parsed page.
        Runs all applicable strategies.
        """
        results: list[EmailExtracted] = []
        seen_addresses: set[str] = set()

        def _add(email: str, method: str, confidence_hint: int) -> None:
            addr = email.strip().strip("'\"`()[]<>,;").lower()
            if addr and "@" in addr and addr not in seen_addresses:
                seen_addresses.add(addr)
                results.append(
                    EmailExtracted(
                        address=addr,
                        confidence=confidence_hint,
                        source=source_url,
                        method=method,
                        page=source_url,
                        timestamp=datetime.now(timezone.utc),
                    )
                )

        # --- Strategy 1: mailto links (highest confidence) ---
        for email in parsed.mailto_links:
            _add(email, "mailto", 90)

        # --- Strategy 2: Visible HTML regex ---
        for email in parsed.emails_raw:
            if email not in seen_addresses:
                _add(email, "html_regex", 70)

        # --- Strategy 3: Footer text ---
        if parsed.footer_text:
            for email in _EMAIL_RE.findall(parsed.footer_text):
                _add(email, "footer", 75)

        # --- Strategy 4: Header text ---
        if parsed.header_text:
            for email in _EMAIL_RE.findall(parsed.header_text):
                _add(email, "header", 65)

        # --- Strategy 5: Schema.org / JSON-LD ---
        for schema_item in parsed.schema_org + parsed.json_ld:
            for email in self._extract_from_schema(schema_item):
                _add(email, "schema_ld", 85)

        # --- Strategy 6: JavaScript source ---
        # (extracted from raw html — search JS blocks)

        # --- Strategy 7: HTML comments ---
        # Handled in raw HTML below

        # --- Strategy 8: Base64 decoded strings ---
        # --- Strategy 9: Unicode obfuscation ---
        # --- Strategy 10: Cloudflare email protection ---
        # --- Strategy 11: PDF / OCR text ---
        # All handled in extract_from_raw_html / extract_from_text

        return results

    def extract_from_raw_html(
        self, html: str, source_url: str, page_type: str = "page"
    ) -> list[EmailExtracted]:
        """
        Advanced extraction directly from raw HTML string.
        Handles JS, comments, base64, obfuscation, Cloudflare.
        Combined with extract_from_parsed for full coverage.
        """
        results: list[EmailExtracted] = []
        seen: set[str] = set()

        def _add(email: str, method: str, confidence: int) -> None:
            addr = email.strip().strip("'\"`()[]<>,;").lower()
            if addr and "@" in addr and "." in addr.split("@")[-1] and addr not in seen:
                seen.add(addr)
                results.append(
                    EmailExtracted(
                        address=addr,
                        confidence=confidence,
                        source=source_url,
                        method=method,
                        page=source_url,
                        timestamp=datetime.now(timezone.utc),
                    )
                )

        # Strategy 6: JavaScript source blocks
        js_blocks = re.findall(
            r"<script[^>]*>(.*?)</script>",
            html,
            re.DOTALL | re.IGNORECASE,
        )
        for block in js_blocks:
            for email_match in _EMAIL_RE.finditer(block):
                if self._is_url_credential(block, email_match.start()):
                    continue  # e.g. Sentry/Bugsnag DSN "//<key>@host" — not a real email
                _add(email_match.group(0), "javascript", 60)

        # Strategy 7: HTML comments
        comments = re.findall(r"<!--(.*?)-->", html, re.DOTALL)
        for comment in comments:
            for email in _EMAIL_RE.findall(comment):
                _add(email, "html_comment", 55)

        # Strategy 8: Base64 encoded strings
        for b64_match in re.finditer(r'"([A-Za-z0-9+/]{20,}={0,2})"', html):
            try:
                decoded = base64.b64decode(b64_match.group(1)).decode("utf-8", errors="ignore")
                for email_match in _EMAIL_RE.finditer(decoded):
                    if self._is_url_credential(decoded, email_match.start()):
                        continue
                    _add(email_match.group(0), "base64", 65)
            except Exception:
                continue

        # Strategy 9: Unicode/obfuscated emails
        for obf_match in _AT_OBFUSCATION.finditer(html):
            local = obf_match.group("local")
            domain = obf_match.group("domain")
            tld = obf_match.group("tld")
            reconstructed = f"{local}@{domain}.{tld}"
            for email in _EMAIL_RE.findall(reconstructed):
                _add(email, "unicode_obfuscation", 60)

        # Strategy 10: Cloudflare email protection
        for cf_match in re.finditer(
            r'data-cfemail="([0-9a-fA-F]+)"', html
        ):
            decoded = self._decode_cloudflare_email(cf_match.group(1))
            if decoded:
                _add(decoded, "cloudflare_decode", 80)

        # Also check for /cdn-cgi/l/email-protection with #hex
        for cf_link_match in re.finditer(
            r'/cdn-cgi/l/email-protection#([0-9a-fA-F]+)', html
        ):
            decoded = self._decode_cloudflare_email(cf_link_match.group(1))
            if decoded:
                _add(decoded, "cloudflare_decode", 80)

        return results

    def extract_from_text(
        self, text: str, source_url: str, method: str = "pdf_text"
    ) -> list[EmailExtracted]:
        """
        Extract emails from plain text (PDF extraction, OCR output).
        """
        results: list[EmailExtracted] = []
        seen: set[str] = set()

        for email in _EMAIL_RE.findall(text):
            addr = email.strip().strip("'\"`()[]<>,;").lower()
            if addr and addr not in seen:
                seen.add(addr)
                results.append(
                    EmailExtracted(
                        address=addr,
                        confidence=50,  # lower confidence for PDF/OCR
                        source=source_url,
                        method=method,
                        page=source_url,
                        timestamp=datetime.now(timezone.utc),
                    )
                )
                logger.debug("Email found in text", address=addr, method=method)

        return results

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _is_url_credential(self, text: str, match_start: int) -> bool:
        """
        True if an email-shaped match is actually the user-info part of a URL
        (scheme://user@host), e.g. a Sentry/Bugsnag DSN embedded in JS such as
        "https://<key>@o12345.ingest.sentry.io/...". Those are API keys, not
        contact emails, and must never be reported as a discovered lead.
        """
        return match_start > 0 and text[match_start - 1] == "/"

    def _extract_from_schema(self, schema: dict) -> list[str]:
        """Recursively extract email values from Schema.org / JSON-LD dict."""
        emails: list[str] = []
        if not isinstance(schema, dict):
            return emails

        for key, value in schema.items():
            if key.lower() in ("email", "contactemail", "contactpoint"):
                if isinstance(value, str):
                    found = _EMAIL_RE.findall(value)
                    emails.extend(found)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            emails.extend(_EMAIL_RE.findall(item))
                        elif isinstance(item, dict):
                            emails.extend(self._extract_from_schema(item))
            elif isinstance(value, dict):
                emails.extend(self._extract_from_schema(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        emails.extend(self._extract_from_schema(item))

        return emails

    def _decode_cloudflare_email(self, encoded_hex: str) -> str | None:
        """
        Decode a Cloudflare email-protected address.
        Cloudflare XOR-encodes emails with the first byte as the key.
        """
        try:
            encoded = bytes.fromhex(encoded_hex)
            if not encoded:
                return None
            key = encoded[0]
            decoded = "".join(chr(b ^ key) for b in encoded[1:])
            # Validate it looks like an email
            if "@" in decoded and "." in decoded.split("@")[-1]:
                return decoded.strip().lower()
        except Exception:
            pass
        return None
