"""
OCR crawler engine — activated only when OCR_ENABLED=true.
Uses PaddleOCR to extract text from images (last resort).
"""

from __future__ import annotations

import time
from typing import Any

from app.config import get_settings
from app.crawler.base_crawler import BaseCrawler, CrawlResponse
from app.logging import get_logger

logger = get_logger(__name__)

_ocr_instance: Any = None


def get_ocr() -> Any:
    """Lazy-load PaddleOCR (heavy dependency)."""
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _ocr_instance


class OcrCrawler(BaseCrawler):
    """
    OCR-based text extraction from images.
    Last resort in the adaptive chain.
    Disabled by default — only activated via OCR_ENABLED=true.
    """

    @property
    def engine_name(self) -> str:
        return "ocr"

    async def crawl(self, url: str, **kwargs: Any) -> CrawlResponse:
        """
        Download an image and run OCR to extract text.
        `url` should be a direct image URL.
        """
        settings = get_settings()
        if not settings.ocr_enabled:
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error="OCR engine disabled by configuration",
            )

        start = time.monotonic()

        try:
            import httpx
            import numpy as np
            from PIL import Image
            import io

            async with httpx.AsyncClient(timeout=30) as client:
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

            # Run OCR
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            img_array = np.array(image)
            ocr = get_ocr()
            result = ocr.ocr(img_array, cls=True)

            # Flatten OCR results to text
            text_lines: list[str] = []
            if result:
                for line_group in result:
                    if line_group:
                        for line in line_group:
                            if line and len(line) >= 2:
                                text_lines.append(line[1][0])

            text = "\n".join(text_lines)
            duration_ms = (time.monotonic() - start) * 1000

            logger.debug(
                "OCR complete",
                url=url,
                text_length=len(text),
                duration_ms=round(duration_ms, 2),
            )

            return CrawlResponse(
                url=url,
                final_url=str(response.url),
                html=text,
                status_code=response.status_code,
                content_type="image/ocr",
                engine=self.engine_name,
                success=True,
                duration_ms=duration_ms,
            )

        except ImportError as exc:
            return CrawlResponse(
                url=url,
                final_url=url,
                html="",
                status_code=None,
                content_type=None,
                engine=self.engine_name,
                success=False,
                error=f"OCR dependency missing: {exc}. Install with: pip install paddleocr",
            )
        except Exception as exc:
            logger.warning("OCR failed", url=url, error=str(exc))
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
