"""
Abstract base crawler interface.
Every engine (HTTP, Playwright, PDF, OCR) implements this interface.
Engines can be swapped without changing business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CrawlResponse:
    """
    Standardized response from any crawler engine.
    Every engine returns this — never raw strings or bytes.
    """

    url: str
    final_url: str
    html: str
    status_code: int | None
    content_type: str | None
    engine: str
    success: bool
    error: str | None = None
    redirect_chain: list[str] = field(default_factory=list)
    response_headers: dict[str, str] = field(default_factory=dict)
    duration_ms: float = 0.0
    raw_bytes: bytes | None = None  # For PDF/image engines


class BaseCrawler(ABC):
    """
    Abstract crawler interface.
    All engines implement: crawl(), parse(), extract(), validate().

    Design:
    - Engines are stateless
    - State lives in Redis and PostgreSQL
    - Engines can be replaced without changing business logic
    """

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Identifier for this engine (e.g. 'http', 'playwright', 'pdf', 'ocr')."""
        ...

    @abstractmethod
    async def crawl(self, url: str, **kwargs: Any) -> CrawlResponse:
        """
        Fetch the resource at `url` and return a CrawlResponse.
        Must handle timeouts, redirects, and errors gracefully.
        Never raise — return CrawlResponse with success=False instead.
        """
        ...

    async def parse(self, response: CrawlResponse) -> dict[str, Any]:
        """
        Parse a CrawlResponse into structured data.
        Returns a dict of extracted fields. Default implementation returns HTML.
        """
        return {"html": response.html, "url": response.final_url}

    async def extract(self, parsed: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract target data (emails, phones, etc.) from parsed data.
        Returns list of extracted items with provenance metadata.
        Default: empty list (override in engines that support this).
        """
        return []

    async def validate(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Validate extracted items. Default: pass-through.
        """
        return items

    async def close(self) -> None:
        """Release resources (connections, browser contexts, etc.)."""
        pass
