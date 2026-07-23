"""
Website issue detector — fully deterministic, zero AI, zero extra crawling.

Built entirely from data the adaptive crawler already collected for a domain
(status codes, headers, timings, parsed HTML). Every check is a small pure
function returning (issue_code, human_readable_text). These are the "problems"
used to build custom outreach emails.

No AI. No randomness. Same crawl data always produces the same issues.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.utils.url_utils import is_contact_page

if TYPE_CHECKING:
    from app.crawler.adaptive_crawler import PageResult
    from app.crawler.base_crawler import CrawlResponse
    from app.parsers.html_parser import ParsedPage

_SLOW_THRESHOLD_MS = 3000.0
_MAX_SUMMARY_LENGTH = 100

_COPYRIGHT_YEAR_RE = re.compile(r"(?:©|copyright)\D{0,10}((?:19|20)\d{2})", re.IGNORECASE)


class IssueDetector:
    """
    Detects observable problems with a crawled website using only evidence
    already gathered during the crawl. Never guesses, never fabricates.
    """

    def detect(
        self,
        homepage_response: "CrawlResponse | None",
        homepage_parsed: "ParsedPage | None",
        pages: list["PageResult"],
    ) -> list[tuple[str, str]]:
        """
        Run all checks against a single crawled domain.
        Returns an ordered list of (issue_code, human_text) — most important first.
        """
        issues: list[tuple[str, str]] = []

        if homepage_response is None or not homepage_response.success:
            issues.append(("unreachable", "Website did not respond or crawl failed"))
            return issues

        issues.extend(self._check_security(homepage_response))
        issues.extend(self._check_status(homepage_response))
        issues.extend(self._check_speed(homepage_response))

        if homepage_parsed is not None:
            issues.extend(self._check_metadata(homepage_parsed))
            issues.extend(self._check_mobile(homepage_parsed))
            issues.extend(self._check_structured_data(homepage_parsed))
            issues.extend(self._check_copyright(homepage_parsed))

        issues.extend(self._check_contact_page(pages))

        return issues

    def summarize(self, issues: list[tuple[str, str]]) -> str:
        """
        Build a deterministic, <=100 character summary from detected issues.
        Always available — free, no external calls.
        """
        if not issues:
            return "No issues detected"

        parts: list[str] = []
        length = 0
        for _, text in issues:
            addition = text if not parts else f"; {text}"
            if length + len(addition) > _MAX_SUMMARY_LENGTH:
                break
            parts.append(text)
            length += len(addition)

        summary = "; ".join(parts)
        return summary[:_MAX_SUMMARY_LENGTH]

    # -------------------------------------------------------------------------
    # Individual checks
    # -------------------------------------------------------------------------

    def _check_security(self, response: "CrawlResponse") -> list[tuple[str, str]]:
        final_url = response.final_url or response.url
        if not final_url.lower().startswith("https://"):
            return [("no_ssl", "No SSL (site not served over HTTPS)")]
        return []

    def _check_status(self, response: "CrawlResponse") -> list[tuple[str, str]]:
        if response.status_code is not None and response.status_code >= 400:
            return [("bad_status", f"Homepage returned HTTP {response.status_code}")]
        return []

    def _check_speed(self, response: "CrawlResponse") -> list[tuple[str, str]]:
        if response.duration_ms and response.duration_ms > _SLOW_THRESHOLD_MS:
            seconds = response.duration_ms / 1000
            return [("slow_load", f"Slow load ({seconds:.1f}s)")]
        return []

    def _check_metadata(self, parsed: "ParsedPage") -> list[tuple[str, str]]:
        issues: list[tuple[str, str]] = []
        if not parsed.title:
            issues.append(("no_title", "Missing page title"))
        if not parsed.description:
            issues.append(("no_meta_description", "Missing meta description"))
        return issues

    def _check_mobile(self, parsed: "ParsedPage") -> list[tuple[str, str]]:
        if "viewport" not in parsed.meta:
            return [("no_viewport", "Not mobile-friendly (no viewport meta tag)")]
        return []

    def _check_structured_data(self, parsed: "ParsedPage") -> list[tuple[str, str]]:
        if not parsed.schema_org and not parsed.json_ld:
            return [("no_structured_data", "No Schema.org/JSON-LD structured data")]
        return []

    def _check_copyright(self, parsed: "ParsedPage") -> list[tuple[str, str]]:
        match = _COPYRIGHT_YEAR_RE.search(parsed.footer_text or "")
        if match:
            year = int(match.group(1))
            current_year = datetime.now(timezone.utc).year
            if current_year - year >= 2:
                return [("outdated_copyright", f"Outdated copyright year ({year})")]
        return []

    def _check_contact_page(self, pages: list["PageResult"]) -> list[tuple[str, str]]:
        for page in pages:
            if is_contact_page(page.url) and page.response.success:
                return []
        return [("no_contact_page", "No working contact/about page found")]
