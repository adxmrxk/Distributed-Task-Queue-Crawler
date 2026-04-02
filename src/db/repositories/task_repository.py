from elasticsearch import Elasticsearch
from typing import Optional
from datetime import datetime, timezone
import uuid
import logging

from src.db.indices import DLQ_INDEX, RETRY_HISTORY_INDEX

logger = logging.getLogger(__name__)


class TaskRepository:

    @staticmethod
    def create_retry_history(
        es: Elasticsearch,
        celery_task_id: str,
        retry_number: int,
        exception_class: Optional[str] = None,
        exception_message: Optional[str] = None,
        backoff_seconds: Optional[int] = None,
        **_kwargs,  # absorb unused SQLAlchemy-era args
    ) -> dict:
        doc = {
            "celery_task_id": celery_task_id,
            "retry_number": retry_number,
            "exception_class": exception_class,
            "exception_message": exception_message,
            "backoff_seconds": backoff_seconds,
            "retried_at": datetime.now(timezone.utc).isoformat(),
        }
        doc_id = str(uuid.uuid4())
        es.index(index=RETRY_HISTORY_INDEX, id=doc_id, document=doc)
        doc["id"] = doc_id
        return doc

    @staticmethod
    def update_task_status(es: Elasticsearch, celery_task_id: str, status: str, **_kwargs) -> None:
        # Task status is tracked inside Celery's result backend (Redis).
        # We only log failures/successes that matter for DLQ.
        logger.debug(f"Task {celery_task_id} status → {status}")

    @staticmethod
    def move_to_dlq(
        es: Elasticsearch,
        job_id: Optional[str],
        celery_task_id: str,
        task_name: str,
        exception_class: Optional[str] = None,
        exception_message: Optional[str] = None,
        traceback: Optional[str] = None,
        total_retries: Optional[int] = None,
        **_kwargs,
    ) -> dict:
        doc = {
            "job_id": job_id,
            "celery_task_id": celery_task_id,
            "task_name": task_name,
            "exception_class": exception_class,
            "exception_message": exception_message,
            "traceback": traceback,
            "total_retries": total_retries,
            "acknowledged": False,
            "final_failure_at": datetime.now(timezone.utc).isoformat(),
        }
        doc_id = str(uuid.uuid4())
        es.index(index=DLQ_INDEX, id=doc_id, document=doc, refresh=True)
        doc["id"] = doc_id
        logger.info(f"Moved task {celery_task_id} to DLQ")
        return doc
