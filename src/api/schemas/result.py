from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BrokenLinkResponse(BaseModel):
    job_id: str
    source_url: str
    broken_url: str
    anchor_text: Optional[str] = None
    status_code: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    depth: Optional[int] = None
    discovered_at: Optional[datetime] = None


class BrokenLinksResponse(BaseModel):
    job_id: str
    total: int
    skip: int
    limit: int
    broken_links: List[BrokenLinkResponse]


class SearchResultItem(BaseModel):
    id: str
    job_id: str
    url: str
    title: Optional[str] = None
    depth: Optional[int] = None
    status_code: Optional[int] = None
    crawled_at: Optional[datetime] = None
    score: Optional[float] = None
    highlights: Optional[dict] = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: List[SearchResultItem]
