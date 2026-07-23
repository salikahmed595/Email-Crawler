"""
Job management routes — CSV import and job status.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.logging import get_logger
from app.queue.queue_manager import QueueManager
from app.services.import_service import ImportService

router = APIRouter(prefix="/jobs", tags=["Jobs"])
logger = get_logger(__name__)

_import_service = ImportService()


@router.post("/import", summary="Import CSV and start crawling")
async def import_csv(file: UploadFile = File(...)) -> dict:
    """
    Upload a CSV file with company domains.
    Validates, creates company records, and enqueues crawl jobs.

    CSV format: company_name,website (or domain,url — auto-detected)
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    try:
        # Create queue manager for this request
        queue_manager = await QueueManager.create()
        try:
            result = await _import_service.import_csv(
                csv_content=content,
                source_file=file.filename,
                queue_manager=queue_manager,
            )
        finally:
            await queue_manager.close()

        return result

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Import failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Import failed")


@router.get("/queue-status", summary="Queue depth and stats")
async def queue_status() -> dict:
    """Returns current queue lengths."""
    try:
        queue_manager = await QueueManager.create()
        try:
            lengths = await queue_manager.get_queue_lengths()
        finally:
            await queue_manager.close()
        return {"queues": lengths}
    except Exception as exc:
        logger.error("Queue status failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Could not reach Redis")
