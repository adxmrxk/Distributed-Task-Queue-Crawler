from fastapi import APIRouter, status
import redis
from src.db.elasticsearch_client import es_client
from src.core.config import settings
from src.worker.celery_app import app as celery_app

router = APIRouter()


@router.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "1.0.0"
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    checks = {
        "elasticsearch": await check_elasticsearch(),
        "redis": await check_redis(),
        "celery": await check_celery()
    }
    all_healthy = all(checks.values())
    return {"ready": all_healthy, "checks": checks}


async def check_elasticsearch() -> bool:
    try:
        return es_client.ping()
    except Exception:
        return False


async def check_redis() -> bool:
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        r.close()
        return True
    except Exception:
        return False


async def check_celery() -> bool:
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        return stats is not None and len(stats) > 0
    except Exception:
        return False
