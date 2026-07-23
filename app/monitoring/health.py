"""
Health checks — verifies DB and Redis connectivity.
"""

from __future__ import annotations

from app.logging import get_logger

logger = get_logger(__name__)


async def check_health() -> dict:
    """
    Check connectivity to all required services.
    Returns status dict suitable for the /health/ready endpoint.
    """
    status = {
        "database": "unknown",
        "redis": "unknown",
        "overall": "unhealthy",
    }

    # Check database
    try:
        from sqlalchemy import text
        from app.storage.database import get_session
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as exc:
        logger.warning("Database health check failed", error=str(exc))
        status["database"] = f"error: {str(exc)[:100]}"

    # Check Redis
    try:
        from app.queue.queue_manager import QueueManager
        qm = await QueueManager.create()
        redis_ok = await qm.ping()
        await qm.close()
        status["redis"] = "ok" if redis_ok else "error: ping failed"
    except Exception as exc:
        logger.warning("Redis health check failed", error=str(exc))
        status["redis"] = f"error: {str(exc)[:100]}"

    # Overall
    if status["database"] == "ok" and status["redis"] == "ok":
        status["overall"] = "healthy"
    elif status["database"] == "ok":
        status["overall"] = "degraded"

    return status
