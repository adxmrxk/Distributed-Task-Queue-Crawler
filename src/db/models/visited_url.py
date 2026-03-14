from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, BigInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.db.base import Base


class VisitedUrl(Base):
    """Visited URLs for deduplication during crawl"""

    __tablename__ = "visited_urls"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('crawl_jobs.id', ondelete='CASCADE'), nullable=False)

    # URL information
    url_hash = Column(String(64), nullable=False)  # SHA256 hash of normalized URL
    original_url = Column(String(2048), nullable=False)
    normalized_url = Column(String(2048), nullable=False)

    # Metadata
    visited_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    depth = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    content_type = Column(String(255), nullable=True)

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('job_id', 'url_hash', name='uq_visited_urls_job_url'),
        Index('idx_visited_urls_job_id', 'job_id'),
    )

    def __repr__(self):
        return f"<VisitedUrl(id={self.id}, url='{self.normalized_url}', depth={self.depth})>"
