"""
Crawl worker — pulls jobs from Redis queue and runs the crawl pipeline.
Stateless: no internal state. All state in Redis + PostgreSQL.
Handles retries, checkpointing, domain locking, and dead-letter.
"""

from __future__ import annotations

import asyncio
import signal
import uuid
from typing import Any

from app.config import get_settings
from app.logging import get_logger
from app.queue.job import CrawlJob
from app.queue.queue_manager import QueueManager
from app.services.crawl_service import CrawlService

logger = get_logger(__name__)


class CrawlWorker:
    """
    Async crawl worker that continuously processes jobs from the queue.

    Features:
    - Graceful shutdown on SIGTERM/SIGINT
    - Domain locking (prevents concurrent crawl of same domain)
    - Automatic retry with exponential backoff
    - Dead-letter queue for exhausted retries
    - Checkpoint: marks domain as crawled to prevent re-crawl within 24h
    """

    def __init__(
        self,
        queue_manager: QueueManager,
        worker_id: str | None = None,
    ) -> None:
        self._queue = queue_manager
        self._worker_id = worker_id or str(uuid.uuid4())[:8]
        self._settings = get_settings()
        self._crawl_service = CrawlService()
        self._running = False
        self._jobs_processed = 0
        self._jobs_failed = 0

    async def start(self) -> None:
        """Start the worker event loop."""
        self._running = True
        logger.info("Crawl worker started", worker_id=self._worker_id)

        # Register graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown)

        try:
            await self._run_loop()
        finally:
            await self._crawl_service.close()
            logger.info(
                "Crawl worker stopped",
                worker_id=self._worker_id,
                jobs_processed=self._jobs_processed,
                jobs_failed=self._jobs_failed,
            )

    async def _run_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                job = await self._queue.dequeue_crawl(timeout=5)
                if job is None:
                    continue  # Queue empty, poll again

                await self._process_job(job)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "Unexpected worker error",
                    worker_id=self._worker_id,
                    error=str(exc),
                )
                await asyncio.sleep(1)

    async def _process_job(self, job: CrawlJob) -> None:
        """Process a single crawl job with locking and retry."""
        domain = job.domain
        company_id = uuid.UUID(job.company_id)

        logger.info(
            "Processing job",
            worker_id=self._worker_id,
            job_id=job.job_id,
            domain=domain,
            retry=job.retry_count,
        )

        # Acquire domain lock — prevents concurrent crawl of same domain
        locked = await self._queue.acquire_domain_lock(
            domain, ttl_seconds=self._settings.job_timeout
        )
        if not locked:
            logger.warning(
                "Domain already locked, requeueing",
                domain=domain,
                job_id=job.job_id,
            )
            await self._queue.enqueue_crawl(job)
            return

        try:
            # Check if recently crawled
            if await self._queue.was_domain_crawled(domain):
                logger.info("Domain recently crawled, skipping", domain=domain)
                return

            await self._crawl_service.process_company(company_id, domain)

            # Mark as crawled (24h TTL)
            await self._queue.mark_domain_crawled(domain)
            self._jobs_processed += 1

            logger.info(
                "Job completed",
                worker_id=self._worker_id,
                job_id=job.job_id,
                domain=domain,
            )

        except Exception as exc:
            self._jobs_failed += 1
            logger.error(
                "Job failed",
                worker_id=self._worker_id,
                job_id=job.job_id,
                domain=domain,
                error=str(exc),
                retry=job.retry_count,
            )
            # Requeue for retry (or dead-letter if max retries exceeded)
            await self._queue.requeue_crawl(job)

        finally:
            await self._queue.release_domain_lock(domain)

    def _shutdown(self) -> None:
        """Signal handler for graceful shutdown."""
        logger.info("Shutdown signal received", worker_id=self._worker_id)
        self._running = False

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "worker_id": self._worker_id,
            "jobs_processed": self._jobs_processed,
            "jobs_failed": self._jobs_failed,
            "running": self._running,
        }
