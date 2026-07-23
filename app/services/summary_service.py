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

from app.config import get_settings
from app.logging import get_logger

logger = get_logger(__name__)

_MAX_SUMMARY_LENGTH = 100


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
