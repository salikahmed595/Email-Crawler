"""
Health check and metrics endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Liveness check")
async def health_check() -> dict:
    """Returns 200 if the API is running."""
    return {"status": "ok", "service": "lead-intelligence-crawler"}


@router.get("/ready", summary="Readiness check")
async def readiness_check() -> dict:
    """Check DB and Redis connectivity."""
    from app.monitoring.health import check_health
    return await check_health()
