from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
import logging
from src.api.schemas.result import BrokenLinksResponse
from src.api.dependencies import get_database
from src.db.repositories.job_repository import JobRepository
from src.db.repositories.link_repository import LinkRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/{job_id}/broken-links",
    response_model=BrokenLinksResponse,
    summary="Get broken links",
    description="Retrieve all broken links found during a crawl job with pagination"
)
async def get_broken_links(
    job_id: UUID,
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results to return"),
    db: Session = Depends(get_database)
):
    """
    Get broken links found in a crawl job

    Returns paginated list of broken links with details about:
    - Source URL (where the broken link was found)
    - Broken URL (the link that's broken)
    - HTTP status code or error type
    - Anchor text
    - Crawl depth
    """
    # Verify job exists
    job = JobRepository.get(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )

    # Get broken links
    broken_links = LinkRepository.get_broken_links_by_job(
        db=db,
        job_id=job_id,
        skip=skip,
        limit=limit
    )

    # Get total count
    total = LinkRepository.count_broken_links_by_job(db, job_id)

    return BrokenLinksResponse(
        job_id=job_id,
        total=total,
        skip=skip,
        limit=limit,
        broken_links=broken_links
    )


@router.get(
    "/{job_id}/summary",
    summary="Get crawl summary",
    description="Get a summary of crawl results including statistics"
)
async def get_crawl_summary(
    job_id: UUID,
    db: Session = Depends(get_database)
):
    """Get summary statistics for a crawl job"""
    job = JobRepository.get(db, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )

    broken_count = LinkRepository.count_broken_links_by_job(db, job_id)

    return {
        "job_id": str(job.id),
        "url": job.url,
        "status": job.status,
        "statistics": {
            "pages_crawled": job.total_pages_crawled,
            "links_found": job.total_links_found,
            "broken_links": broken_count,
            "max_depth": job.max_depth,
            "max_pages": job.max_pages
        },
        "timestamps": {
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at
        },
        "error": job.error_message
    }
