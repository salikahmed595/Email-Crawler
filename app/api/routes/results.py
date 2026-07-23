"""
Results routes — fetch company records and trigger exports.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.logging import get_logger
from app.services.export_service import ExportService
from app.storage.database import get_session
from app.storage.repositories.company_repo import CompanyRepository
from app.storage.repositories.email_repo import EmailRepository

router = APIRouter(prefix="/results", tags=["Results"])
logger = get_logger(__name__)

_export_service = ExportService()


@router.get("/companies", summary="List all companies with status")
async def list_companies(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """List companies with pagination."""
    async with get_session() as session:
        repo = CompanyRepository(session)
        if status:
            companies = await repo.list_by_status(status, limit=limit, offset=offset)
        else:
            companies = await repo.list_all(limit=limit, offset=offset)

    return {
        "total": len(companies),
        "offset": offset,
        "companies": [
            {
                "id": str(c.id),
                "domain": c.domain,
                "name": c.name,
                "status": c.status,
                "retry_count": c.retry_count,
            }
            for c in companies
        ],
    }


@router.get("/companies/{company_id}", summary="Get full company record")
async def get_company(company_id: str) -> dict:
    """Get a single company with all emails and metadata."""
    result = await _export_service.get_company_export(company_id)
    if not result:
        raise HTTPException(status_code=404, detail="Company not found")
    return result


@router.post("/export", summary="Export all results to JSON")
async def export_results(
    min_confidence: int = Query(0, ge=0, le=100),
) -> dict:
    """Trigger a full JSON export and return the file path."""
    try:
        path = await _export_service.export_to_json(min_confidence=min_confidence)
        return {"status": "exported", "path": path}
    except Exception as exc:
        logger.error("Export failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Export failed")


@router.get("/stats", summary="Crawl statistics")
async def get_stats() -> dict:
    """Overall statistics: company counts by status, email counts."""
    async with get_session() as session:
        company_repo = CompanyRepository(session)
        email_repo = EmailRepository(session)

        status_counts = await company_repo.count_by_status()
        valid_emails = await email_repo.count_valid()

    return {
        "companies": status_counts,
        "emails": {"total_valid": valid_emails},
    }
