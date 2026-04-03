from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Centralized configuration using Pydantic Settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Application
    APP_NAME: str = "Distributed Web Crawler"
    DEBUG: bool = False

    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # Redis
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50

    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300
    CELERY_TASK_TIME_LIMIT: int = 360

    # Crawler Configuration
    CRAWLER_USER_AGENT: str = "DistributedCrawler/1.0 (+https://example.com/bot)"
    CRAWLER_DEFAULT_TIMEOUT: int = 30
    CRAWLER_MAX_DEPTH: int = 3
    CRAWLER_MAX_PAGES: int = 100
    CRAWLER_RESPECT_ROBOTS: bool = True
    CRAWLER_RATE_LIMIT_PER_DOMAIN: float = 1.0

    # Retry Configuration
    RETRY_MAX_ATTEMPTS: int = 5
    RETRY_BACKOFF_BASE: int = 60
    RETRY_BACKOFF_MAX: int = 600

    # Dead Letter Queue
    DLQ_ENABLED: bool = True
    DLQ_ALERT_WEBHOOK: Optional[str] = None

    # Auth — JWT
    # Generate a secret: python -c "import secrets; print(secrets.token_hex(32))"
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # Auth — credentials
    # Generate hash: python -c "from passlib.hash import bcrypt; print(bcrypt.hash('yourpassword'))"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = "$2b$12$placeholder-replace-with-real-bcrypt-hash"

    # Auth — API key for programmatic access (optional)
    API_KEY: Optional[str] = None


settings = Settings()
