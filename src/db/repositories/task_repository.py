from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from src.db.models.task_metadata import TaskMetadata
from src.db.models.retry_history import RetryHistory
from src.db.models.dlq import DeadLetterQueue


class TaskRepository:
    """Repository for task-related operations"""

    @staticmethod
    def create_task_metadata(
        db: Session,
        job_id: UUID,
        celery_task_id: str,
        task_name: str,
        status: str,
        args: Optional[dict] = None,
        kwargs: Optional[dict] = None
    ) -> TaskMetadata:
        """Create task metadata record"""
        metadata = TaskMetadata(
            job_id=job_id,
            celery_task_id=celery_task_id,
            task_name=task_name,
            status=status,
            args=args,
            kwargs=kwargs
        )
        db.add(metadata)
        db.commit()
        db.refresh(metadata)
        return metadata

    @staticmethod
    def update_task_status(
        db: Session,
        celery_task_id: str,
        status: str,
        result: Optional[dict] = None,
        exception_class: Optional[str] = None,
        exception_message: Optional[str] = None,
        traceback: Optional[str] = None
    ) -> Optional[TaskMetadata]:
        """Update task status"""
        task = db.query(TaskMetadata).filter(
            TaskMetadata.celery_task_id == celery_task_id
        ).first()

        if task:
            task.status = status
            if result:
                task.result = result
            if exception_class:
                task.exception_class = exception_class
            if exception_message:
                task.exception_message = exception_message
            if traceback:
                task.traceback = traceback

            if status == "STARTED" and not task.started_at:
                task.started_at = datetime.utcnow()
            elif status in ["SUCCESS", "FAILURE"]:
                task.completed_at = datetime.utcnow()

            db.commit()
            db.refresh(task)
        return task

    @staticmethod
    def create_retry_history(
        db: Session,
        task_metadata_id: Optional[int],
        celery_task_id: str,
        retry_number: int,
        exception_class: Optional[str] = None,
        exception_message: Optional[str] = None,
        next_retry_eta: Optional[datetime] = None,
        backoff_seconds: Optional[int] = None
    ) -> RetryHistory:
        """Create retry history record"""
        retry = RetryHistory(
            task_metadata_id=task_metadata_id,
            celery_task_id=celery_task_id,
            retry_number=retry_number,
            exception_class=exception_class,
            exception_message=exception_message,
            next_retry_eta=next_retry_eta,
            backoff_seconds=backoff_seconds
        )
        db.add(retry)
        db.commit()
        db.refresh(retry)
        return retry

    @staticmethod
    def move_to_dlq(
        db: Session,
        job_id: Optional[UUID],
        celery_task_id: str,
        task_name: str,
        args: Optional[dict] = None,
        kwargs: Optional[dict] = None,
        exception_class: Optional[str] = None,
        exception_message: Optional[str] = None,
        traceback: Optional[str] = None,
        total_retries: Optional[int] = None,
        first_failure_at: Optional[datetime] = None
    ) -> DeadLetterQueue:
        """Move a task to the dead letter queue"""
        dlq_entry = DeadLetterQueue(
            job_id=job_id,
            celery_task_id=celery_task_id,
            task_name=task_name,
            args=args,
            kwargs=kwargs,
            exception_class=exception_class,
            exception_message=exception_message,
            traceback=traceback,
            total_retries=total_retries,
            first_failure_at=first_failure_at
        )
        db.add(dlq_entry)
        db.commit()
        db.refresh(dlq_entry)
        return dlq_entry

    @staticmethod
    def get_unacknowledged_dlq_entries(
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[DeadLetterQueue]:
        """Get unacknowledged DLQ entries"""
        return db.query(DeadLetterQueue).filter(
            DeadLetterQueue.acknowledged == False
        ).order_by(
            DeadLetterQueue.final_failure_at.desc()
        ).offset(skip).limit(limit).all()

    @staticmethod
    def acknowledge_dlq_entry(
        db: Session,
        dlq_id: int,
        acknowledged_by: str,
        notes: Optional[str] = None
    ) -> Optional[DeadLetterQueue]:
        """Acknowledge a DLQ entry"""
        entry = db.query(DeadLetterQueue).filter(DeadLetterQueue.id == dlq_id).first()
        if entry:
            entry.acknowledged = True
            entry.acknowledged_at = datetime.utcnow()
            entry.acknowledged_by = acknowledged_by
            if notes:
                entry.notes = notes
            db.commit()
            db.refresh(entry)
        return entry
