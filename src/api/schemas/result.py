from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class BrokenLinkResponse(BaseModel):
    """Response schema for a single broken link"""
    id: int
    job_id: UUID
    source_url: str
    broken_url: str
    anchor_text: Optional[str] = None
    status_code: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    depth: Optional[int] = None
    discovered_at: datetime

    class Config:
        from_attributes = True


class BrokenLinksResponse(BaseModel):
    """Response schema for paginated broken links"""
    job_id: UUID
    total: int
    skip: int
    limit: int
    broken_links: List[BrokenLinkResponse]
