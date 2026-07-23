"""Crawler package."""
from app.crawler.adaptive_crawler import AdaptiveCrawler, DomainCrawlResult, PageResult
from app.crawler.base_crawler import BaseCrawler, CrawlResponse
from app.crawler.http_crawler import HttpCrawler
from app.crawler.ocr_crawler import OcrCrawler
from app.crawler.pdf_crawler import PdfCrawler
from app.crawler.playwright_crawler import PlaywrightCrawler

__all__ = [
    "BaseCrawler",
    "CrawlResponse",
    "HttpCrawler",
    "PlaywrightCrawler",
    "PdfCrawler",
    "OcrCrawler",
    "AdaptiveCrawler",
    "DomainCrawlResult",
    "PageResult",
]
