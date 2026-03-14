from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, Enum):
    """Celery task status enumeration"""
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class LinkErrorType(str, Enum):
    """Link validation error types"""
    HTTP_ERROR = "HTTP_ERROR"
    TIMEOUT = "TIMEOUT"
    DNS_ERROR = "DNS_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    SSL_ERROR = "SSL_ERROR"
    INVALID_URL = "INVALID_URL"


# HTTP Status codes
HTTP_SUCCESS_MIN = 200
HTTP_SUCCESS_MAX = 299
HTTP_CLIENT_ERROR_MIN = 400
HTTP_SERVER_ERROR_MIN = 500

# Crawling defaults
DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_PAGES = 100
DEFAULT_TIMEOUT = 30

# Rate limiting
DEFAULT_RATE_LIMIT = 1.0  # requests per second
DEFAULT_BURST_CAPACITY = 5  # max burst requests

# Retry configuration
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_BACKOFF_BASE = 60  # seconds
DEFAULT_RETRY_BACKOFF_MAX = 600  # 10 minutes
