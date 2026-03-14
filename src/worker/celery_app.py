from celery import Celery
from kombu import Queue, Exchange
from src.core.config import settings
from src.core.logging import setup_logging

# Initialize logging
setup_logging()

# Create Celery app
app = Celery('distributed_crawler')

# Configure Celery with production-grade settings
app.conf.update(
    # Broker and backend
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,

    # Critical reliability settings
    task_acks_late=True,  # Only acknowledge task after completion
    task_reject_on_worker_lost=True,  # Re-queue if worker crashes
    worker_prefetch_multiplier=1,  # One task at a time for long-running tasks

    # Task execution limits
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,  # 5 minutes soft
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,  # 6 minutes hard

    # Result backend settings
    result_expires=86400,  # 24 hours
    result_extended=True,  # Store additional metadata
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
    },

    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task routing
    task_routes={
        'src.worker.tasks.crawler.crawl_url': {'queue': 'crawler'},
        'src.worker.tasks.link_checker.check_link': {'queue': 'link_checker'},
        'src.worker.tasks.link_checker.check_links_batch': {'queue': 'link_checker'},
    },

    # Queue definitions with priority support
    task_queues=(
        Queue(
            'crawler',
            Exchange('crawler'),
            routing_key='crawler',
            queue_arguments={'x-max-priority': 10}
        ),
        Queue(
            'link_checker',
            Exchange('link_checker'),
            routing_key='link_checker',
            queue_arguments={'x-max-priority': 10}
        ),
        Queue(
            'dlq',
            Exchange('dlq'),
            routing_key='dlq'
        ),
    ),

    # Default queue
    task_default_queue='crawler',
    task_default_exchange='crawler',
    task_default_routing_key='crawler',

    # Worker settings
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)
    worker_disable_rate_limits=False,

    # Beat scheduler (for periodic tasks if needed)
    beat_schedule={},

    # Event settings
    worker_send_task_events=True,
    task_send_sent_event=True,

    # Ignore result for fire-and-forget tasks
    task_ignore_result=False,

    # Task track started
    task_track_started=True,
)

# Import tasks to register them
from src.worker.tasks import crawler, link_checker

__all__ = ['app']
