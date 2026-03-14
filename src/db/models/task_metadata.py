from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from src.db.base import Base


class TaskMetadata(Base):
    """Task metadata for tracking Celery task executions"""

    __tablename__ = "task_metadata"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('crawl_jobs.id', ondelete='CASCADE'), nullable=False)
    celery_task_id = Column(String(255), nullable=False, unique=True)
    task_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)  # PENDING, STARTED, RETRY, SUCCESS, FAILURE

    # Task data
    args = Column(JSONB, nullable=True)
    kwargs = Column(JSONB, nullable=True)
    result = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Worker information
    worker_name = Column(String(255), nullable=True)

    # Error information
    exception_class = Column(String(255), nullable=True)
    exception_message = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_task_metadata_job_id', 'job_id'),
        Index('idx_task_metadata_celery_task_id', 'celery_task_id'),
        Index('idx_task_metadata_status', 'status'),
        Index('idx_task_metadata_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<TaskMetadata(id={self.id}, task_id='{self.celery_task_id}', status='{self.status}')>"
