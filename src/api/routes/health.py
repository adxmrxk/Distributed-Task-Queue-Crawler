from fastapi import APIRouter, status
from sqlalchemy import text
import redis
from src.db.session import engine
from src.core.config import settings
from src.worker.celery_app import app as celery_app

router = APIRouter()


@router.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "1.0.0"
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    """
    Readiness check - verifies all dependencies are available
    Returns 503 if any dependency is unhealthy
    """
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "celery": await check_celery()
    }

    all_healthy = all(checks.values())
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "ready": all_healthy,
        "checks": checks
    }


async def check_database() -> bool:
    """Check if database is accessible"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis() -> bool:
    """Check if Redis is accessible"""
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        redis_client.close()
        return True
    except Exception:
        return False


async def check_celery() -> bool:
    """Check if Celery workers are available"""
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        return stats is not None and len(stats) > 0
    except Exception:
        return False
