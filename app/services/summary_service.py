"""
Summary service — optional, last-resort polish layer on top of the
deterministic issue summary produced by IssueDetector.

The crawler and issue detection NEVER depend on this. This module is only
invoked when the caller explicitly opts in (settings.openai_enabled AND an
API key is configured AND the dashboard checkbox is ticked for the run).
On any error, missing key, or timeout it falls back to the deterministic
summary unchanged — it never blocks or fails the pipeline.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.logging import get_logger

logger = get_logger(__name__)

_MAX_SUMMARY_LENGTH = 100
_MAX_BUSINESS_SUMMARY_LENGTH = 800
_NO_BUSINESS_DATA = "No business description found on site."


class SummaryService:
    """Optional AI polish for website-issue summaries. Off by default."""

    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def available(self) -> bool:
        """Whether OpenAI polishing is configured and enabled."""
        return bool(self._settings.openai_enabled and self._settings.openai_api_key)

    async def polish(
        self,
        company_name: str | None,
        issues: list[tuple[str, str]],
        deterministic_summary: str,
    ) -> str:
        """
        Attempt to rewrite the deterministic issue summary in more natural
        language via OpenAI. Always falls back to the deterministic summary.
        """
        if not self.available or not issues:
            return deterministic_summary

        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning("openai package not installed; skipping summary polish")
            return deterministic_summary

        issue_text = "; ".join(text for _, text in issues)
        prompt = (
            f"Rewrite this list of website problems for '{company_name or 'this business'}' "
            f"as one natural sentence, strictly under {_MAX_SUMMARY_LENGTH} characters, "
            f"no preamble, no quotes: {issue_text}"
        )

        try:
            client = AsyncOpenAI(api_key=self._settings.openai_api_key)
            response = await client.chat.completions.create(
                model=self._settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,
                temperature=0.3,
                timeout=10,
            )
            polished = (response.choices[0].message.content or "").strip().strip('"')
            if polished:
                return polished[:_MAX_SUMMARY_LENGTH]
        except Exception as exc:
            logger.warning("OpenAI summary polish failed, using deterministic summary", error=str(exc))

        return deterministic_summary

    def deterministic_business_summary(self, company_metadata: dict[str, Any] | None) -> str:
        """
        Build a "what do they do" summary purely from facts already
        extracted from the site (meta/schema description, services,
        industry) — never invented. Honest "no data" message if the site
        published nothing usable.
        """
        metadata = company_metadata or {}
        description = (metadata.get("description") or "").strip()
        services = [s for s in (metadata.get("services") or []) if s]
        industry = metadata.get("industry") or metadata.get("category")

        parts: list[str] = []
        if description:
            parts.append(description)
        if services:
            parts.append("Services: " + ", ".join(services[:6]) + ".")
        if industry:
            parts.append(f"Industry: {industry}.")

        if not parts:
            return _NO_BUSINESS_DATA
        return " ".join(parts)[:_MAX_BUSINESS_SUMMARY_LENGTH]

    async def business_summary(
        self,
        company_name: str | None,
        deterministic_summary: str,
    ) -> str:
        """
        Optionally rewrite the deterministic business summary into a
        natural 3-4 sentence description via OpenAI — using ONLY the real
        extracted facts already in `deterministic_summary` as input, never
        adding new facts. Always falls back to the deterministic version.
        """
        if not self.available or deterministic_summary == _NO_BUSINESS_DATA:
            return deterministic_summary

        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning("openai package not installed; skipping business summary polish")
            return deterministic_summary

        prompt = (
            f"Using ONLY the facts below about the business "
            f"'{company_name or 'this business'}', write a 3-4 sentence summary "
            f"of what they do and how. Do not invent, assume, or add any fact "
            f"that isn't stated below.\n\nFacts: {deterministic_summary}"
        )

        try:
            client = AsyncOpenAI(api_key=self._settings.openai_api_key)
            response = await client.chat.completions.create(
                model=self._settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
                timeout=12,
            )
            polished = (response.choices[0].message.content or "").strip().strip('"')
            if polished:
                return polished[:_MAX_BUSINESS_SUMMARY_LENGTH]
        except Exception as exc:
            logger.warning(
                "OpenAI business summary polish failed, using deterministic summary",
                error=str(exc),
            )

        return deterministic_summary
