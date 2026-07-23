"""
Redis-backed async queue manager.
Supports: enqueue, dequeue, ack, retry, dead-letter, queue length.
All state lives in Redis — workers are stateless.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from app.config import get_settings
from app.queue.job import CrawlJob, ExportJob, ValidationJob

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class QueueManager:
    """
    Manages Redis-backed queues for the crawl pipeline. Only used by the
    optional Docker/Postgres "Queue Mode" — the local dashboard never
    imports this module's `redis` dependency.

    Queue names are configured via environment variables.
    Uses Redis lists (LPUSH / BRPOP) for FIFO queues.
    Uses Redis sorted sets for priority queues.
    """

    def __init__(self, redis_client: "aioredis.Redis") -> None:
        self._redis = redis_client
        self._settings = get_settings()

    # -------------------------------------------------------------------------
    # Connection factory
    # -------------------------------------------------------------------------
    @classmethod
    async def create(cls) -> "QueueManager":
        """Create a QueueManager with a fresh Redis connection."""
        import redis.asyncio as aioredis

        settings = get_settings()
        client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        return cls(client)

    async def close(self) -> None:
        await self._redis.aclose()

    # -------------------------------------------------------------------------
    # Crawl Queue
    # -------------------------------------------------------------------------
    async def enqueue_crawl(self, job: CrawlJob) -> None:
        """Add a crawl job to the queue."""
        queue_name = self._settings.crawl_queue_name
        payload = json.dumps(job.to_dict())
        await self._redis.lpush(queue_name, payload)
        logger.debug("Enqueued crawl job", extra={"job_id": job.job_id, "domain": job.domain})

    async def dequeue_crawl(self, timeout: int = 5) -> CrawlJob | None:
        """Block-pop a crawl job from the queue."""
        queue_name = self._settings.crawl_queue_name
        result = await self._redis.brpop(queue_name, timeout=timeout)
        if result is None:
            return None
        _, payload = result
        data = json.loads(payload)
        return CrawlJob.from_dict(data)

    async def requeue_crawl(self, job: CrawlJob) -> None:
        """Re-enqueue a failed job for retry."""
        if job.retry_count >= self._settings.max_job_retries:
            await self._move_to_dead_letter(job.to_dict(), "crawl")
            logger.warning(
                "Job moved to dead letter after max retries",
                extra={"job_id": job.job_id, "domain": job.domain},
            )
            return
        job.retry_count += 1
        await self.enqueue_crawl(job)
        logger.info(
            "Re-enqueued crawl job",
            extra={"job_id": job.job_id, "retry": job.retry_count},
        )

    # -------------------------------------------------------------------------
    # Validation Queue
    # -------------------------------------------------------------------------
    async def enqueue_validation(self, job: ValidationJob) -> None:
        queue_name = self._settings.validation_queue_name
        payload = json.dumps(job.to_dict())
        await self._redis.lpush(queue_name, payload)

    async def dequeue_validation(self, timeout: int = 5) -> ValidationJob | None:
        queue_name = self._settings.validation_queue_name
        result = await self._redis.brpop(queue_name, timeout=timeout)
        if result is None:
            return None
        _, payload = result
        return ValidationJob.from_dict(json.loads(payload))

    # -------------------------------------------------------------------------
    # Export Queue
    # -------------------------------------------------------------------------
    async def enqueue_export(self, job: ExportJob) -> None:
        queue_name = self._settings.export_queue_name
        payload = json.dumps(job.to_dict())
        await self._redis.lpush(queue_name, payload)

    async def dequeue_export(self, timeout: int = 5) -> ExportJob | None:
        queue_name = self._settings.export_queue_name
        result = await self._redis.brpop(queue_name, timeout=timeout)
        if result is None:
            return None
        _, payload = result
        return ExportJob.from_dict(json.loads(payload))

    # -------------------------------------------------------------------------
    # Dead Letter
    # -------------------------------------------------------------------------
    async def _move_to_dead_letter(
        self, job_data: dict[str, Any], source_queue: str
    ) -> None:
        """Move failed jobs to dead letter queue for inspection."""
        dead_letter_name = self._settings.dead_letter_queue_name
        job_data["dead_letter_source"] = source_queue
        payload = json.dumps(job_data)
        await self._redis.lpush(dead_letter_name, payload)

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------
    async def get_queue_lengths(self) -> dict[str, int]:
        """Return current length of all queues."""
        settings = self._settings
        queues = [
            settings.crawl_queue_name,
            settings.validation_queue_name,
            settings.export_queue_name,
            settings.dead_letter_queue_name,
        ]
        lengths: dict[str, int] = {}
        for queue in queues:
            length = await self._redis.llen(queue)
            lengths[queue] = length
        return lengths

    # -------------------------------------------------------------------------
    # Rate limiting (per domain)
    # -------------------------------------------------------------------------
    async def acquire_domain_lock(self, domain: str, ttl_seconds: int = 60) -> bool:
        """
        Attempt to acquire a per-domain lock.
        Returns True if acquired, False if domain is currently being crawled.
        """
        key = f"lock:domain:{domain}"
        acquired = await self._redis.set(key, "1", ex=ttl_seconds, nx=True)
        return acquired is not None

    async def release_domain_lock(self, domain: str) -> None:
        """Release the per-domain lock after crawl completes."""
        key = f"lock:domain:{domain}"
        await self._redis.delete(key)

    # -------------------------------------------------------------------------
    # Dedup cache
    # -------------------------------------------------------------------------
    async def mark_domain_crawled(self, domain: str, ttl_seconds: int = 86400) -> None:
        """Mark a domain as recently crawled (24hr TTL by default)."""
        key = f"crawled:{domain}"
        await self._redis.set(key, "1", ex=ttl_seconds)

    async def was_domain_crawled(self, domain: str) -> bool:
        """Check if a domain was crawled recently."""
        key = f"crawled:{domain}"
        return await self._redis.exists(key) > 0

    # -------------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------------
    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            return await self._redis.ping()
        except Exception:
            return False
