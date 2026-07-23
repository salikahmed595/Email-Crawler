"""Models package."""
from app.models.base import Base, TimestampMixin
from app.models.company import Company
from app.models.crawl_result import CrawlResult
from app.models.email import Email

__all__ = ["Base", "TimestampMixin", "Company", "Email", "CrawlResult"]
