from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

from src.api.routes import health, jobs, results, search
from src.core.logging import setup_logging
from src.core.config import settings
from src.db.elasticsearch_client import get_es_client
from src.db.indices import create_indices

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Distributed Web Crawler API",
    description="""
    Production-grade distributed web crawler with Elasticsearch-backed search.

    ## Features
    * **Full Browser Automation**: JavaScript rendering with Playwright
    * **Broken Link Detection**: Comprehensive link validation
    * **Distributed Processing**: Celery workers with Redis broker
    * **Full-Text Search**: Every crawled page is indexed in Elasticsearch
    * **Production Ready**: Dead letter queue, exponential backoff, rate limiting
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.APP_NAME}")
    try:
        es = get_es_client()
        create_indices(es)
        logger.info("Elasticsearch indices ready")
    except Exception as e:
        logger.error(f"Failed to initialize Elasticsearch indices: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {settings.APP_NAME}")


app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(results.router, prefix="/api/v1/results", tags=["Results"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Distributed Web Crawler API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "search": "/api/v1/search?q=your+query",
    }
