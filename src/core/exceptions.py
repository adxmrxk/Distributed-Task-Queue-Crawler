class CrawlerException(Exception):
    """Base exception for crawler errors"""
    pass


class InvalidURLException(CrawlerException):
    """Raised when a URL is invalid or malformed"""
    pass


class RateLimitExceededException(CrawlerException):
    """Raised when rate limit is exceeded"""
    pass


class RobotsTxtDeniedException(CrawlerException):
    """Raised when robots.txt denies access"""
    pass


class CrawlTimeoutException(CrawlerException):
    """Raised when crawl operation times out"""
    pass


class DatabaseException(CrawlerException):
    """Raised for database-related errors"""
    pass


class TaskException(CrawlerException):
    """Raised for Celery task-related errors"""
    pass


class PlaywrightException(CrawlerException):
    """Raised for Playwright-related errors"""
    pass
