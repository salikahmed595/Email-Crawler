"""
PDF crawler — extracts text from PDF documents using PyMuPDF.
Activated only when PDF_ENABLED=true and static/playwright crawling
fails to find sufficient email data.
"""

from __future__ import annotations

import io
import time
from typing import Any

from app.config import get_settings
from app.crawler.base_crawler import BaseCrawler, CrawlResponse
from app.logging import get_logger

logger = get_logger(__name__)


class PdfCrawler(BaseCrawler):
    """
    PDF text extraction engine using PyMuPDF (fitz).
    Handles PDFs linked from company websites.
    """

    @property
    def engine_name(self) -> str:
        return "pdf"

    async def crawl(self, url: str, **kwargs: Any) -> CrawlResponse:
        """
        Download a PDF and extract its text content.
        The text is returned as `html` field for consistent interface.
        """
        settings = get_settings()
        if not settings.pdf_enabled:
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error="PDF engine disabled by configuration",
            )

        start = time.monotonic()

        try:
            import fitz  # PyMuPDF

            # Download the PDF
            import httpx

            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": settings.user_agent},
            ) as client:
                response = await client.get(url)

            if response.status_code >= 400:
                return CrawlResponse(
                    url=url,
                    final_url=url,
                    html="",
                    status_code=response.status_code,
                    content_type=None,
                    engine=self.engine_name,
                    success=False,
                    error=f"HTTP {response.status_code}",
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            # Extract text from PDF
            pdf_bytes = response.content
            text_content = self._extract_text(pdf_bytes)
            duration_ms = (time.monotonic() - start) * 1000

            logger.debug(
                "PDF crawl complete",
                url=url,
                text_length=len(text_content),
                duration_ms=round(duration_ms, 2),
            )

            return CrawlResponse(
                url=url,
                final_url=str(response.url),
                html=text_content,  # text stored in html field
                status_code=response.status_code,
                content_type="application/pdf",
                engine=self.engine_name,
                success=True,
                duration_ms=duration_ms,
                raw_bytes=pdf_bytes,
            )

        except ImportError:
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error="PyMuPDF not installed. Run: pip install pymupdf",
            )
        except Exception as exc:
            logger.warning("PDF crawl failed", url=url, error=str(exc))
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )

    def _extract_text(self, pdf_bytes: bytes) -> str:
        """Extract all text from a PDF document."""
        import fitz  # PyMuPDF

        text_parts: list[str] = []
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    text_parts.append(text)
        finally:
            doc.close()
        return "\n".join(text_parts)
