from fastapi import APIRouter, HTTPException, Depends, Query
from elasticsearch import Elasticsearch
import logging

from src.api.schemas.result import BrokenLinksResponse
from src.api.dependencies import get_es
from src.db.repositories.job_repository import JobRepository
from src.db.repositories.link_repository import LinkRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{job_id}/broken-links", response_model=BrokenLinksResponse)
async def get_broken_links(
    job_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    es: Elasticsearch = Depends(get_es),
):
    job = JobRepository.get(es, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    broken_links = LinkRepository.get_broken_links_by_job(es=es, job_id=job_id, skip=skip, limit=limit)
    total = LinkRepository.count_broken_links_by_job(es, job_id)

    return BrokenLinksResponse(job_id=job_id, total=total, skip=skip, limit=limit, broken_links=broken_links)


@router.get("/{job_id}/summary")
async def get_crawl_summary(job_id: str, es: Elasticsearch = Depends(get_es)):
    job = JobRepository.get(es, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return {
        "job_id": job_id,
        "url": job["url"],
        "status": job["status"],
        "statistics": {
            "pages_crawled": job["total_pages_crawled"],
            "links_found": job["total_links_found"],
            "broken_links": job["total_broken_links"],
            "max_depth": job["max_depth"],
            "max_pages": job["max_pages"],
        },
        "timestamps": {
            "created_at": job["created_at"],
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
        },
        "error": job.get("error_message"),
    }
