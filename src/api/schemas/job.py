from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class JobCreateRequest(BaseModel):
    url: str = Field(..., description="Starting URL to crawl", max_length=2048)
    max_depth: int = Field(default=3, ge=1, le=10)
    max_pages: int = Field(default=100, ge=1, le=10000)
    respect_robots_txt: bool = Field(default=True)

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "max_depth": 3,
                "max_pages": 100,
                "respect_robots_txt": True,
            }
        }


class JobResponse(BaseModel):
    id: str
    url: str
    status: str
    max_depth: int
    max_pages: int
    respect_robots_txt: bool
    created_at: datetime
    celery_task_id: Optional[str] = None


class JobStatusResponse(BaseModel):
    id: str
    url: str
    status: str
    max_depth: int
    max_pages: int
    respect_robots_txt: bool
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_pages_crawled: int = 0
    total_links_found: int = 0
    total_broken_links: int = 0
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None


class JobListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    jobs: List[JobStatusResponse]
