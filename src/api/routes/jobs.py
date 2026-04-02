from fastapi import APIRouter, HTTPException, Depends, status, Query
from elasticsearch import Elasticsearch
from typing import Optional
import logging

from src.api.schemas.job import JobCreateRequest, JobResponse, JobStatusResponse, JobListResponse
from src.api.dependencies import get_es
from src.db.repositories.job_repository import JobRepository
from src.worker.tasks.crawler import crawl_url
from src.core.constants import JobStatus
from src.utils.url_utils import validate_url
from src.worker.celery_app import app as celery_app
from src.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(request: JobCreateRequest, es: Elasticsearch = Depends(get_es)):
    if not validate_url(request.url):
        raise HTTPException(status_code=400, detail=f"Invalid URL: {request.url}")

    try:
        job = JobRepository.create(
            es=es,
            url=request.url,
            max_depth=request.max_depth,
            max_pages=request.max_pages,
            respect_robots_txt=request.respect_robots_txt,
        )

        task = crawl_url.apply_async(args=[job["id"], request.url, 0], queue="crawler")

        JobRepository.update_celery_task_id(es, job["id"], task.id)
        JobRepository.update_status(es, job["id"], JobStatus.IN_PROGRESS.value)

        job["celery_task_id"] = task.id
        job["status"] = JobStatus.IN_PROGRESS.value

        logger.info("Created crawl job", extra={"job_id": job["id"], "url": request.url})
        return job

    except Exception as e:
        logger.error(f"Failed to create job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create crawl job")


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    es: Elasticsearch = Depends(get_es),
):
    jobs = JobRepository.list_jobs(es=es, skip=skip, limit=limit, status=status)
    return JobListResponse(total=len(jobs), skip=skip, limit=limit, jobs=jobs)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, es: Elasticsearch = Depends(get_es)):
    job = JobRepository.get(es, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
async def cancel_job(job_id: str, es: Elasticsearch = Depends(get_es)):
    job = JobRepository.get(es, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job["status"] in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
        raise HTTPException(status_code=400, detail=f"Job is already {job['status']} and cannot be cancelled")

    try:
        if job.get("celery_task_id"):
            celery_app.control.revoke(job["celery_task_id"], terminate=True, signal="SIGTERM")

        JobRepository.update_status(es, job_id, JobStatus.CANCELLED.value)
        return {"message": "Job cancelled successfully", "job_id": job_id}

    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel job")
