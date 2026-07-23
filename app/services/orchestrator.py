"""
Local batch orchestrator — runs the full crawl pipeline for a CSV of
companies directly on this machine. No Redis, no Docker, no job queue:
just a bounded pool of concurrent "crawling agents" (asyncio tasks) sharing
one local SQLite file.

This is the engine behind the dashboard's "Start Crawl" button.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from app.config import get_settings
from app.logging import get_logger
from app.services.crawl_service import CrawlService
from app.services.import_service import ImportService
from app.storage.database import get_session, init_db
from app.storage.repositories.company_repo import CompanyRepository

logger = get_logger(__name__)


@dataclass
class CompanyProgress:
    """One row of live progress reported back to the caller (the dashboard)."""

    domain: str
    name: str | None
    status: str  # "crawling" | "done" | "failed"
    result: dict[str, Any] | None = None
    error: str | None = None


ProgressCallback = Callable[[CompanyProgress], None]


class LocalBatchRunner:
    """
    Imports a CSV and crawls every company using a bounded pool of
    concurrent crawling agents (default 5-7, configurable), processed in
    batches (default 100) so a single run has a predictable, bounded footprint.
    """

    def __init__(self, use_ai_summary: bool = False) -> None:
        self._settings = get_settings()
        self._use_ai_summary = use_ai_summary

    async def run(
        self,
        csv_content: str | bytes,
        source_file: str,
        progress_cb: ProgressCallback | None = None,
    ) -> list[CompanyProgress]:
        """
        Import the CSV and crawl every pending company.
        Companies already crawled (any status besides "pending") in a
        previous run against the same database are skipped, not re-crawled.
        """
        await init_db()

        import_service = ImportService()
        import_summary = await import_service.import_csv(
            csv_content=csv_content,
            source_file=source_file,
            queue_manager=None,
        )
        logger.info(
            "CSV imported for local batch run",
            **{k: v for k, v in import_summary.items() if k != "errors"},
        )

        async with get_session() as session:
            repo = CompanyRepository(session)
            companies = await repo.list_by_status("pending", limit=1_000_000)

        results: list[CompanyProgress] = []
        crawl_service = CrawlService()
        concurrency = max(5, min(self._settings.concurrent_crawlers, 7))
        semaphore = asyncio.Semaphore(concurrency)
        batch_size = max(1, self._settings.batch_size)

        logger.info(
            "Starting local batch crawl",
            companies=len(companies),
            concurrency=concurrency,
            batch_size=batch_size,
        )

        async def crawl_one(company) -> None:
            async with semaphore:
                if progress_cb:
                    progress_cb(
                        CompanyProgress(domain=company.domain, name=company.name, status="crawling")
                    )
                try:
                    result = await crawl_service.process_company(
                        company.id, company.domain, use_ai_summary=self._use_ai_summary
                    )
                    # A Maps listing's placeholder domain may have been
                    # resolved to the real business domain mid-crawl —
                    # reflect that in the reported result, not the stale
                    # placeholder captured before this task started.
                    progress = CompanyProgress(
                        domain=result.get("domain") or company.domain,
                        name=company.name,
                        status="done",
                        result=result,
                    )
                except Exception as exc:
                    logger.error("Company crawl failed", domain=company.domain, error=str(exc))
                    progress = CompanyProgress(
                        domain=company.domain, name=company.name, status="failed", error=str(exc)
                    )
                results.append(progress)
                if progress_cb:
                    progress_cb(progress)

        try:
            for start in range(0, len(companies), batch_size):
                batch = companies[start : start + batch_size]
                await asyncio.gather(*(crawl_one(c) for c in batch))
        finally:
            await crawl_service.close()

        logger.info("Local batch crawl complete", total=len(results))
        return results
