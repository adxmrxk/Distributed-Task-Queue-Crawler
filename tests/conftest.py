"""
Root conftest.py — sets required environment variables before any src imports
so that pydantic-settings can create the Settings() singleton at module load time.
"""
import os

# Must be set before any src.* import triggers Settings() creation
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/15"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/14"

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient


@pytest.fixture
def mock_db():
    """A MagicMock that stands in for a SQLAlchemy Session."""
    return MagicMock()


@pytest.fixture
def sample_job_id():
    return uuid4()


@pytest.fixture
def api_client(mock_db):
    """
    FastAPI TestClient with the database dependency overridden to use a mock
    session and Celery task dispatch patched out.
    """
    from src.api.main import app
    from src.api.dependencies import get_database

    app.dependency_overrides[get_database] = lambda: mock_db

    with patch("src.worker.tasks.crawler.crawl_url") as _mock_task:
        _mock_task.apply_async.return_value.id = "test-task-id-abc"
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()
