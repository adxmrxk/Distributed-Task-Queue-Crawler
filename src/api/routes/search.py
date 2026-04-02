from fastapi import APIRouter, Depends, Query
from elasticsearch import Elasticsearch
from typing import Optional
import logging

from src.api.schemas.result import SearchResponse
from src.api.dependencies import get_es
from src.db.repositories.page_repository import PageRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=SearchResponse)
async def search_pages(
    q: str = Query(..., min_length=1, description="Search query"),
    job_id: Optional[str] = Query(None, description="Scope search to a specific crawl job"),
    size: int = Query(20, ge=1, le=100),
    es: Elasticsearch = Depends(get_es),
):
    """
    Full-text search across all crawled page content.

    Searches page titles (boosted 3x) and body text using English-language
    analysis. Optionally scoped to a single job. Returns matching pages with
    highlighted snippets showing where the query appears.
    """
    results = PageRepository.search(es=es, query=q, job_id=job_id, size=size)

    return SearchResponse(query=q, total=len(results), results=results)
