"""
Integration tests for JobRepository using a mocked SQLAlchemy session.

These tests verify that the repository methods issue the correct ORM calls
and apply the expected business logic (status transitions, timestamps, etc.)
without requiring a live database.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

from src.db.repositories.job_repository import JobRepository
from src.db.models.job import CrawlJob
from src.core.constants import JobStatus


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def existing_job():
    """A realistic CrawlJob instance with all fields populated."""
    job = MagicMock(spec=CrawlJob)
    job.id = uuid4()
    job.url = "https://example.com"
    job.status = JobStatus.PENDING.value
    job.celery_task_id = None
    job.started_at = None
    job.completed_at = None
    job.total_pages_crawled = 0
    job.total_links_found = 0
    job.total_broken_links = 0
    job.error_message = None
    return job


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

class TestJobRepositoryCreate:
    def test_adds_and_commits(self, db):
        JobRepository.create(db, url="https://example.com")
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_returns_crawl_job_instance(self, db):
        job = JobRepository.create(db, url="https://example.com")
        assert isinstance(job, CrawlJob)

    def test_sets_pending_status(self, db):
        job = JobRepository.create(db, url="https://example.com")
        assert job.status == JobStatus.PENDING.value

    def test_passes_custom_depth_and_pages(self, db):
        job = JobRepository.create(db, url="https://example.com", max_depth=5, max_pages=500)
        assert job.max_depth == 5
        assert job.max_pages == 500

    def test_respects_robots_txt_default_true(self, db):
        job = JobRepository.create(db, url="https://example.com")
        assert job.respect_robots_txt is True

    def test_user_id_stored(self, db):
        job = JobRepository.create(db, url="https://example.com", user_id="user-42")
        assert job.user_id == "user-42"


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestJobRepositoryGet:
    def test_queries_by_id(self, db, existing_job):
        db.query.return_value.filter.return_value.first.return_value = existing_job
        result = JobRepository.get(db, existing_job.id)
        db.query.assert_called_with(CrawlJob)
        assert result is existing_job

    def test_returns_none_when_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = JobRepository.get(db, uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------

class TestJobRepositoryListJobs:
    def test_returns_all_without_filters(self, db, existing_job):
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [existing_job]
        result = JobRepository.list_jobs(db)
        assert existing_job in result

    def test_applies_status_filter(self, db):
        db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        JobRepository.list_jobs(db, status=JobStatus.COMPLETED.value)
        # filter() should have been called (once for status)
        db.query.return_value.filter.assert_called()

    def test_applies_user_id_filter(self, db):
        db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        JobRepository.list_jobs(db, user_id="user-1")
        db.query.return_value.filter.assert_called()


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------

class TestJobRepositoryUpdateStatus:
    def test_sets_started_at_on_in_progress(self, db, existing_job):
        db.query.return_value.filter.return_value.first.return_value = existing_job
        existing_job.started_at = None

        JobRepository.update_status(db, existing_job.id, JobStatus.IN_PROGRESS.value)

        assert existing_job.status == JobStatus.IN_PROGRESS.value
        assert existing_job.started_at is not None
        db.commit.assert_called_once()

    def test_sets_completed_at_on_completed(self, db, existing_job):
        db.query.return_value.filter.return_value.first.return_value = existing_job

        JobRepository.update_status(db, existing_job.id, JobStatus.COMPLETED.value)

        assert existing_job.completed_at is not None

    def test_sets_completed_at_on_failed(self, db, existing_job):
        db.query.return_value.filter.return_value.first.return_value = existing_job

        JobRepository.update_status(db, existing_job.id, JobStatus.FAILED.value)

        assert existing_job.completed_at is not None

    def test_stores_error_message(self, db, existing_job):
        db.query.return_value.filter.return_value.first.return_value = existing_job

        JobRepository.update_status(db, existing_job.id, JobStatus.FAILED.value, error_message="Timeout")

        assert existing_job.error_message == "Timeout"

    def test_returns_none_when_job_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None

        result = JobRepository.update_status(db, uuid4(), JobStatus.COMPLETED.value)

        assert result is None

    def test_does_not_overwrite_started_at_if_already_set(self, db, existing_job):
        original_time = datetime(2026, 1, 1)
        existing_job.started_at = original_time
        db.query.return_value.filter.return_value.first.return_value = existing_job

        JobRepository.update_status(db, existing_job.id, JobStatus.IN_PROGRESS.value)

        assert existing_job.started_at == original_time


# ---------------------------------------------------------------------------
# update_celery_task_id
# ---------------------------------------------------------------------------

class TestJobRepositoryUpdateCeleryTaskId:
    def test_stores_task_id(self, db, existing_job):
        db.query.return_value.filter.return_value.first.return_value = existing_job

        JobRepository.update_celery_task_id(db, existing_job.id, "celery-abc-123")

        assert existing_job.celery_task_id == "celery-abc-123"
        db.commit.assert_called_once()

    def test_returns_none_when_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = JobRepository.update_celery_task_id(db, uuid4(), "task-id")
        assert result is None


# ---------------------------------------------------------------------------
# increment counters
# ---------------------------------------------------------------------------

class TestJobRepositoryIncrements:
    def test_increment_pages_crawled(self, db, existing_job):
        existing_job.total_pages_crawled = 5
        db.query.return_value.filter.return_value.first.return_value = existing_job

        JobRepository.increment_pages_crawled(db, existing_job.id)

        assert existing_job.total_pages_crawled == 6

    def test_increment_links_found_default_1(self, db, existing_job):
        existing_job.total_links_found = 10
        db.query.return_value.filter.return_value.first.return_value = existing_job

        JobRepository.increment_links_found(db, existing_job.id)

        assert existing_job.total_links_found == 11

    def test_increment_links_found_by_count(self, db, existing_job):
        existing_job.total_links_found = 0
        db.query.return_value.filter.return_value.first.return_value = existing_job

        JobRepository.increment_links_found(db, existing_job.id, count=5)

        assert existing_job.total_links_found == 5

    def test_increment_broken_links(self, db, existing_job):
        existing_job.total_broken_links = 2
        db.query.return_value.filter.return_value.first.return_value = existing_job

        JobRepository.increment_broken_links(db, existing_job.id)

        assert existing_job.total_broken_links == 3


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestJobRepositoryDelete:
    def test_deletes_and_returns_true(self, db, existing_job):
        db.query.return_value.filter.return_value.first.return_value = existing_job

        result = JobRepository.delete(db, existing_job.id)

        db.delete.assert_called_once_with(existing_job)
        db.commit.assert_called_once()
        assert result is True

    def test_returns_false_when_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None

        result = JobRepository.delete(db, uuid4())

        assert result is False
