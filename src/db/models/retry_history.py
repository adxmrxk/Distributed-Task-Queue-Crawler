from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index, BigInteger
from sqlalchemy.sql import func
from src.db.base import Base


class RetryHistory(Base):
    """Retry history for tracking task retry attempts"""

    __tablename__ = "retry_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_metadata_id = Column(BigInteger, ForeignKey('task_metadata.id', ondelete='CASCADE'), nullable=True)
    celery_task_id = Column(String(255), nullable=False)
    retry_number = Column(Integer, nullable=False)

    # Exception information
    exception_class = Column(String(255), nullable=True)
    exception_message = Column(Text, nullable=True)

    # Retry timing
    retry_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    next_retry_eta = Column(DateTime(timezone=True), nullable=True)
    backoff_seconds = Column(Integer, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_retry_history_task_metadata_id', 'task_metadata_id'),
        Index('idx_retry_history_celery_task_id', 'celery_task_id'),
    )

    def __repr__(self):
        return f"<RetryHistory(id={self.id}, task_id='{self.celery_task_id}', retry={self.retry_number})>"
