from celery import Task
import logging
from src.core.config import settings
from src.utils.retry_utils import calculate_exponential_backoff
from src.db.elasticsearch_client import es_client
from src.db.repositories.task_repository import TaskRepository

logger = logging.getLogger(__name__)


class BaseTaskWithRetry(Task):
    """
    Base task class with exponential backoff retry logic and DLQ integration

    Features:
    - Automatic exponential backoff with jitter
    - Dead Letter Queue for permanently failed tasks
    - Task metadata tracking
    - Retry history logging
    """

    # Exceptions to auto-retry
    autoretry_for = (
        ConnectionError,
        TimeoutError,
        Exception,  # Retry most exceptions
    )

    # Don't retry these exceptions
    dont_retry = (
        ValueError,  # Invalid input
        TypeError,   # Programming error
    )

    # Retry configuration
    max_retries = settings.RETRY_MAX_ATTEMPTS
    retry_backoff = True
    retry_backoff_max = settings.RETRY_BACKOFF_MAX
    retry_jitter = True

    def before_start(self, task_id, args, kwargs):
        """Called before task execution starts"""
        logger.info(
            f"Task starting: {self.name}",
            extra={
                'task_id': task_id,
                'task_name': self.name,
            }
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried"""
        retry_count = self.request.retries
        backoff = calculate_exponential_backoff(retry_count)

        logger.warning(
            f"Task retry #{retry_count}: {self.name}",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'retry_count': retry_count,
                'exception': str(exc),
                'backoff_seconds': backoff
            }
        )

        # Log retry to database
        try:
            TaskRepository.create_retry_history(
                es=es_client,
                celery_task_id=task_id,
                retry_number=retry_count,
                exception_class=exc.__class__.__name__,
                exception_message=str(exc),
                backoff_seconds=backoff,
            )
        except Exception as e:
            logger.error(f"Failed to log retry history: {e}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails permanently (after max retries)"""
        logger.error(
            f"Task failed permanently: {self.name}",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'exception': str(exc),
                'traceback': str(einfo.traceback),
                'total_retries': self.request.retries
            }
        )

        # Move to Dead Letter Queue if enabled
        if settings.DLQ_ENABLED:
            self._move_to_dlq(task_id, args, kwargs, exc, einfo)

        # Update task metadata
        try:
            TaskRepository.update_task_status(es=es_client, celery_task_id=task_id, status='FAILURE')
        except Exception as e:
            logger.error(f"Failed to update task metadata: {e}")

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task completes successfully"""
        logger.info(
            f"Task succeeded: {self.name}",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'result': retval
            }
        )

        # Update task metadata
        try:
            TaskRepository.update_task_status(es=es_client, celery_task_id=task_id, status='SUCCESS')
        except Exception as e:
            logger.error(f"Failed to update task metadata: {e}")

    def _move_to_dlq(self, task_id, args, kwargs, exc, einfo):
        """Move failed task to Dead Letter Queue"""
        try:
            job_id = kwargs.get('job_id') or (args[0] if args else None)
            TaskRepository.move_to_dlq(
                es=es_client,
                job_id=job_id,
                celery_task_id=task_id,
                task_name=self.name,
                exception_class=exc.__class__.__name__,
                exception_message=str(exc),
                traceback=str(einfo.traceback),
                total_retries=self.request.retries,
            )
        except Exception as e:
            logger.error(f"Failed to move task to DLQ: {e}")

    def apply_async_with_retry(self, args=None, kwargs=None, **options):
        """
        Apply task asynchronously with retry configuration

        Convenience method to apply tasks with pre-configured retry settings
        """
        countdown = calculate_exponential_backoff(0)

        return self.apply_async(
            args=args,
            kwargs=kwargs,
            countdown=countdown,
            **options
        )
