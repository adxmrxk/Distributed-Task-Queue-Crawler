from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
from src.api.routes import health, jobs, results
from src.core.logging import setup_logging
from src.core.config import settings

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Distributed Web Crawler API",
    description="""
    Production-grade distributed web crawler with broken link detection.

    ## Features

    * **Full Browser Automation**: JavaScript rendering with Playwright
    * **Broken Link Detection**: Comprehensive link validation
    * **Distributed Processing**: Celery workers with Redis broker
    * **Production Ready**: Dead letter queue, exponential backoff, rate limiting
    * **Politeness**: Respects robots.txt and crawl-delay directives

    ## Usage

    1. Submit a crawl job via POST /api/v1/jobs
    2. Monitor progress via GET /api/v1/jobs/{job_id}
    3. Retrieve broken links via GET /api/v1/results/{job_id}/broken-links
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error"
        }
    )


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    logger.info(f"Starting {settings.APP_NAME}")
    logger.info(f"Debug mode: {settings.DEBUG}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    logger.info(f"Shutting down {settings.APP_NAME}")


# Include routers
app.include_router(
    health.router,
    prefix="/health",
    tags=["Health"]
)

app.include_router(
    jobs.router,
    prefix="/api/v1/jobs",
    tags=["Jobs"]
)

app.include_router(
    results.router,
    prefix="/api/v1/results",
    tags=["Results"]
)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """API root endpoint"""
    return {
        "message": "Distributed Web Crawler API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "ready": "/health/ready"
    }
