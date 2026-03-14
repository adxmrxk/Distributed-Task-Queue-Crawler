from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class JobCreateRequest(BaseModel):
    """Request schema for creating a new crawl job"""
    url: str = Field(..., description="Starting URL to crawl", max_length=2048)
    max_depth: int = Field(default=3, ge=1, le=10, description="Maximum crawl depth")
    max_pages: int = Field(default=100, ge=1, le=10000, description="Maximum pages to crawl")
    respect_robots_txt: bool = Field(default=True, description="Respect robots.txt")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "max_depth": 3,
                "max_pages": 100,
                "respect_robots_txt": True
            }
        }


class JobResponse(BaseModel):
    """Response schema for job creation"""
    id: UUID
    url: str
    status: str
    max_depth: int
    max_pages: int
    respect_robots_txt: bool
    created_at: datetime
    celery_task_id: Optional[str] = None

    class Config:
        from_attributes = True


class JobStatusResponse(BaseModel):
    """Response schema for job status query"""
    id: UUID
    url: str
    status: str
    max_depth: int
    max_pages: int
    respect_robots_txt: bool
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_pages_crawled: int
    total_links_found: int
    total_broken_links: int
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Response schema for listing jobs"""
    total: int
    skip: int
    limit: int
    jobs: List[JobStatusResponse]
