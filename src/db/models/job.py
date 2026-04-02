from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from src.db.base import Base
from src.core.constants import JobStatus


class CrawlJob(Base):
    """Crawl job model representing a web crawling task"""

    __tablename__ = "crawl_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String(2048), nullable=False)
    status = Column(String(50), nullable=False, default=JobStatus.PENDING.value)

    # Configuration
    max_depth = Column(Integer, default=3)
    max_pages = Column(Integer, default=100)
    respect_robots_txt = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Statistics
    total_pages_crawled = Column(Integer, default=0)
    total_links_found = Column(Integer, default=0)
    total_broken_links = Column(Integer, default=0)

    # Task tracking
    celery_task_id = Column(String(255), nullable=True)
    user_id = Column(String(255), nullable=True)  # For multi-tenancy

    # Error handling
    error_message = Column(Text, nullable=True)

    # Flexible metadata storage
    job_metadata = Column(JSONB, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_crawl_jobs_status', 'status'),
        Index('idx_crawl_jobs_created_at', 'created_at'),
        Index('idx_crawl_jobs_user_id', 'user_id'),
        Index('idx_crawl_jobs_celery_task_id', 'celery_task_id'),
    )

    def __repr__(self):
        return f"<CrawlJob(id={self.id}, url='{self.url}', status='{self.status}')>"
