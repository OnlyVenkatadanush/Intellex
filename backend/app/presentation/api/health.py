import time
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.database import get_db
from backend.app.config import settings

router = APIRouter(prefix="/api", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """
    Basic liveness probe — returns 200 if the service is running.
    Used by Docker, Kubernetes, and load balancers.
    """
    return {
        "status": "healthy",
        "service": "intellex-api",
        "version": "1.1.0",
        "environment": settings.ENVIRONMENT
    }


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed readiness probe — checks database connectivity.
    Returns component-level health status.
    """
    checks = {}
    overall = "healthy"

    # ── Database Check ────────────────────────────────────────────────────────
    db_start = time.monotonic()
    try:
        db.execute(text("SELECT 1"))
        db_latency_ms = int((time.monotonic() - db_start) * 1000)
        checks["database"] = {
            "status": "healthy",
            "latency_ms": db_latency_ms,
            "engine": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql"
        }
    except Exception as exc:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(exc)
        }
        overall = "degraded"
        logger.error(f"Health check: database connection failed — {exc}")

    return {
        "status": overall,
        "service": "intellex-api",
        "version": "1.1.0",
        "environment": settings.ENVIRONMENT,
        "components": checks
    }
