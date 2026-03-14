from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Index, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from src.db.base import Base


class DeadLetterQueue(Base):
    """Dead Letter Queue for permanently failed tasks"""

    __tablename__ = "dead_letter_queue"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('crawl_jobs.id', ondelete='SET NULL'), nullable=True)
    celery_task_id = Column(String(255), nullable=False)
    task_name = Column(String(255), nullable=False)

    # Task data
    args = Column(JSONB, nullable=True)
    kwargs = Column(JSONB, nullable=True)

    # Failure information
    exception_class = Column(String(255), nullable=True)
    exception_message = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)
    total_retries = Column(Integer, nullable=True)

    # Timestamps
    first_failure_at = Column(DateTime(timezone=True), nullable=True)
    final_failure_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Acknowledgment workflow
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_dlq_job_id', 'job_id'),
        Index('idx_dlq_acknowledged', 'acknowledged'),
        Index('idx_dlq_final_failure_at', 'final_failure_at'),
    )

    def __repr__(self):
        return f"<DeadLetterQueue(id={self.id}, task_id='{self.celery_task_id}', ack={self.acknowledged})>"
