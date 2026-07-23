"""
Export worker — triggers JSON export jobs from the queue.
"""

from __future__ import annotations

import asyncio

from app.logging import get_logger
from app.queue.job import ExportJob
from app.queue.queue_manager import QueueManager
from app.services.export_service import ExportService

logger = get_logger(__name__)


class ExportWorker:
    """Async worker that handles export jobs."""

    def __init__(self, queue_manager: QueueManager) -> None:
        self._queue = queue_manager
        self._export_service = ExportService()
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Export worker started")
        try:
            while self._running:
                job = await self._queue.dequeue_export(timeout=5)
                if job is None:
                    continue
                await self._process_job(job)
        finally:
            logger.info("Export worker stopped")

    async def _process_job(self, job: ExportJob) -> None:
        logger.info("Processing export job", job_id=job.job_id, output=job.output_path)
        try:
            path = await self._export_service.export_to_json(
                output_path=job.output_path,
                min_confidence=job.min_confidence,
            )
            logger.info("Export job completed", job_id=job.job_id, path=path)
        except Exception as exc:
            logger.error("Export job failed", job_id=job.job_id, error=str(exc))

    def stop(self) -> None:
        self._running = False
