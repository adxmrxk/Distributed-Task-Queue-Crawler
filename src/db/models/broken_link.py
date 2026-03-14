from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.db.base import Base


class BrokenLink(Base):
    """Broken link model for storing detected broken links"""

    __tablename__ = "broken_links"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('crawl_jobs.id', ondelete='CASCADE'), nullable=False)

    # Link information
    source_url = Column(String(2048), nullable=False)  # Page where link was found
    broken_url = Column(String(2048), nullable=False)  # The broken link
    anchor_text = Column(Text, nullable=True)  # Link text for context

    # Error details
    status_code = Column(Integer, nullable=True)  # HTTP status (404, 500, etc.)
    error_type = Column(String(100), nullable=True)  # TIMEOUT, DNS_ERROR, etc.
    error_message = Column(Text, nullable=True)

    # Metadata
    discovered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    depth = Column(Integer, nullable=True)  # Crawl depth where discovered
    retry_count = Column(Integer, default=0)  # Verification retries

    # Indexes
    __table_args__ = (
        Index('idx_broken_links_job_id', 'job_id'),
        Index('idx_broken_links_status_code', 'status_code'),
        Index('idx_broken_links_error_type', 'error_type'),
    )

    def __repr__(self):
        return f"<BrokenLink(id={self.id}, broken_url='{self.broken_url}', status={self.status_code})>"
