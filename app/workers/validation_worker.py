"""
Validation worker — picks up validation jobs and runs the email validator.
"""

from __future__ import annotations

import asyncio
import uuid

from app.config import get_settings
from app.logging import get_logger
from app.queue.job import ValidationJob
from app.queue.queue_manager import QueueManager
from app.storage.database import get_session
from app.storage.repositories.email_repo import EmailRepository
from app.validators.email_validator import EmailValidator

logger = get_logger(__name__)


class ValidationWorker:
    """Async worker that validates emails from the validation queue."""

    def __init__(self, queue_manager: QueueManager) -> None:
        self._queue = queue_manager
        self._validator = EmailValidator()
        self._settings = get_settings()
        self._running = False

    async def start(self) -> None:
        """Start the validation worker loop."""
        self._running = True
        logger.info("Validation worker started")
        try:
            while self._running:
                job = await self._queue.dequeue_validation(timeout=5)
                if job is None:
                    continue
                await self._process_job(job)
        finally:
            logger.info("Validation worker stopped")

    async def _process_job(self, job: ValidationJob) -> None:
        """Validate all emails in the job."""
        logger.info(
            "Processing validation job",
            job_id=job.job_id,
            email_count=len(job.email_ids),
        )
        try:
            async with get_session() as session:
                email_repo = EmailRepository(session)
                for email_id_str in job.email_ids:
                    try:
                        email_id = uuid.UUID(email_id_str)
                        email = await email_repo.get_by_id(email_id)
                        if not email:
                            continue

                        result = await self._validator.validate(email.address)
                        await email_repo.update_validation(
                            email_id,
                            {
                                "is_valid_syntax": result.is_valid_syntax,
                                "is_valid_domain": result.is_valid_domain,
                                "mx_valid": result.mx_valid,
                                "smtp_valid": result.smtp_valid,
                                "is_disposable": result.is_disposable,
                                "is_role_based": result.is_role_based,
                                "confidence": result.confidence,
                                "validation_status": result.validation_status,
                                "notes": "; ".join(result.notes) if result.notes else None,
                            },
                        )
                    except Exception as exc:
                        logger.error(
                            "Email validation failed",
                            email_id=email_id_str,
                            error=str(exc),
                        )
        except Exception as exc:
            logger.error(
                "Validation job failed", job_id=job.job_id, error=str(exc)
            )

    def stop(self) -> None:
        self._running = False
