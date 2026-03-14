from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
import logging
from src.api.schemas.job import (
    JobCreateRequest,
    JobResponse,
    JobStatusResponse,
    JobListResponse
)
from src.api.dependencies import get_database
from src.db.repositories.job_repository import JobRepository
from src.worker.tasks.crawler import crawl_url
from src.core.constants import JobStatus
from src.utils.url_utils import validate_url
from src.worker.celery_app import app as celery_app

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new crawl job",
    description="Submit a new web crawling job. Returns immediately with job ID while crawling happens in background."
)
async def create_job(
    request: JobCreateRequest,
    db: Session = Depends(get_database)
):
    """
    Create a new crawl job

    - **url**: Starting URL to crawl (must be valid HTTP/HTTPS URL)
    - **max_depth**: Maximum crawl depth (1-10, default: 3)
    - **max_pages**: Maximum pages to crawl (1-10000, default: 100)
    - **respect_robots_txt**: Whether to respect robots.txt (default: true)
    """
    # Validate URL
    if not validate_url(request.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL: {request.url}"
        )

    try:
        # Create job in database
        job = JobRepository.create(
            db=db,
            url=request.url,
            max_depth=request.max_depth,
            max_pages=request.max_pages,
            respect_robots_txt=request.respect_robots_txt
        )

        logger.info(
            f"Created crawl job",
            extra={
                'job_id': str(job.id),
                'url': request.url,
                'max_depth': request.max_depth
            }
        )

        # Dispatch initial crawl task to Celery
        task = crawl_url.apply_async(
            args=[str(job.id), request.url, 0],
            queue='crawler'
        )

        # Update job with Celery task ID and set status to IN_PROGRESS
        JobRepository.update_celery_task_id(db, job.id, task.id)
        JobRepository.update_status(db, job.id, JobStatus.IN_PROGRESS.value)

        # Refresh to get updated data
        db.refresh(job)

        logger.info(
            f"Dispatched crawl task",
            extra={
                'job_id': str(job.id),
                'task_id': task.id
            }
        )

        return job

    except Exception as e:
        logger.error(f"Failed to create job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create crawl job"
        )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Retrieve the current status and statistics of a crawl job"
)
async def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_database)
):
    """Get detailed status of a crawl job"""
    job = JobRepository.get(db, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )

    return job


@router.get(
    "/",
    response_model=JobListResponse,
    summary="List all jobs",
    description="List all crawl jobs with optional filtering by status"
)
async def list_jobs(
    skip: int = Query(0, ge=0, description="Number of jobs to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of jobs to return"),
    status: Optional[str] = Query(None, description="Filter by job status"),
    db: Session = Depends(get_database)
):
    """List all crawl jobs with pagination and optional filtering"""
    jobs = JobRepository.list_jobs(
        db=db,
        skip=skip,
        limit=limit,
        status=status
    )

    # Get total count (simplified - in production, do a separate count query)
    total = len(jobs)

    return JobListResponse(
        total=total,
        skip=skip,
        limit=limit,
        jobs=jobs
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel a job",
    description="Cancel a running crawl job and revoke all associated tasks"
)
async def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_database)
):
    """Cancel a running crawl job"""
    job = JobRepository.get(db, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )

    # Check if job can be cancelled
    if job.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is already {job.status} and cannot be cancelled"
        )

    try:
        # Revoke Celery tasks
        if job.celery_task_id:
            celery_app.control.revoke(job.celery_task_id, terminate=True, signal='SIGTERM')

        # Update job status
        JobRepository.update_status(db, job.id, JobStatus.CANCELLED.value)

        logger.info(
            f"Cancelled job",
            extra={'job_id': str(job_id)}
        )

        return {
            "message": "Job cancelled successfully",
            "job_id": str(job_id)
        }

    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel job"
        )
