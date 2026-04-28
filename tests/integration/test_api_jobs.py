"""
Integration tests for the FastAPI jobs router.

Uses FastAPI's TestClient with the database dependency overridden to a mock
session and Celery task dispatch patched out, so no live services are needed.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.core.constants import JobStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_job(
    url="https://example.com",
    status=JobStatus.IN_PROGRESS.value,
    celery_task_id="task-abc",
    max_depth=3,
    max_pages=100,
    respect_robots_txt=True,
    total_pages_crawled=0,
    total_links_found=0,
    total_broken_links=0,
    started_at=None,
    completed_at=None,
    error_message=None,
):
    job = MagicMock()
    job.id = uuid4()
    job.url = url
    job.status = status
    job.celery_task_id = celery_task_id
    job.max_depth = max_depth
    job.max_pages = max_pages
    job.respect_robots_txt = respect_robots_txt
    job.created_at = datetime(2026, 3, 16, 10, 0, 0)
    job.started_at = started_at
    job.completed_at = completed_at
    job.total_pages_crawled = total_pages_crawled
    job.total_links_found = total_links_found
    job.total_broken_links = total_broken_links
    job.error_message = error_message
    return job


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/
# ---------------------------------------------------------------------------

class TestCreateJob:
    def test_create_job_returns_201(self, api_client, mock_db):
        mock_job = make_mock_job()

        with patch("src.api.routes.jobs.JobRepository.create", return_value=mock_job), \
             patch("src.api.routes.jobs.crawl_url") as mock_task, \
             patch("src.api.routes.jobs.JobRepository.update_celery_task_id"), \
             patch("src.api.routes.jobs.JobRepository.update_status"):

            mock_task.apply_async.return_value.id = "task-abc"
            mock_db.refresh = MagicMock()

            response = api_client.post("/api/v1/jobs/", json={
                "url": "https://example.com",
                "max_depth": 3,
                "max_pages": 100,
                "respect_robots_txt": True
            })

        assert response.status_code == 201

    def test_create_job_response_contains_id(self, api_client, mock_db):
        mock_job = make_mock_job()

        with patch("src.api.routes.jobs.JobRepository.create", return_value=mock_job), \
             patch("src.api.routes.jobs.crawl_url") as mock_task, \
             patch("src.api.routes.jobs.JobRepository.update_celery_task_id"), \
             patch("src.api.routes.jobs.JobRepository.update_status"):

            mock_task.apply_async.return_value.id = "task-abc"
            mock_db.refresh = MagicMock()

            response = api_client.post("/api/v1/jobs/", json={"url": "https://example.com"})

        body = response.json()
        assert "id" in body

    def test_create_job_invalid_url_returns_400(self, api_client):
        response = api_client.post("/api/v1/jobs/", json={"url": "not-a-valid-url"})
        assert response.status_code == 400

    def test_create_job_ftp_url_returns_400(self, api_client):
        response = api_client.post("/api/v1/jobs/", json={"url": "ftp://example.com"})
        assert response.status_code == 400

    def test_create_job_missing_url_returns_422(self, api_client):
        response = api_client.post("/api/v1/jobs/", json={"max_depth": 3})
        assert response.status_code == 422

    def test_create_job_dispatches_celery_task(self, api_client, mock_db):
        mock_job = make_mock_job()

        with patch("src.api.routes.jobs.JobRepository.create", return_value=mock_job), \
             patch("src.api.routes.jobs.crawl_url") as mock_task, \
             patch("src.api.routes.jobs.JobRepository.update_celery_task_id"), \
             patch("src.api.routes.jobs.JobRepository.update_status"):

            mock_task.apply_async.return_value.id = "task-abc"
            mock_db.refresh = MagicMock()

            api_client.post("/api/v1/jobs/", json={"url": "https://example.com"})

            mock_task.apply_async.assert_called_once()

    def test_create_job_updates_celery_task_id(self, api_client, mock_db):
        mock_job = make_mock_job()

        with patch("src.api.routes.jobs.JobRepository.create", return_value=mock_job), \
             patch("src.api.routes.jobs.crawl_url") as mock_task, \
             patch("src.api.routes.jobs.JobRepository.update_celery_task_id") as mock_update_tid, \
             patch("src.api.routes.jobs.JobRepository.update_status"):

            mock_task.apply_async.return_value.id = "task-xyz"
            mock_db.refresh = MagicMock()

            api_client.post("/api/v1/jobs/", json={"url": "https://example.com"})

            mock_update_tid.assert_called_once()
            args = mock_update_tid.call_args[0]
            assert args[2] == "task-xyz"

    def test_create_job_sets_status_in_progress(self, api_client, mock_db):
        mock_job = make_mock_job()

        with patch("src.api.routes.jobs.JobRepository.create", return_value=mock_job), \
             patch("src.api.routes.jobs.crawl_url") as mock_task, \
             patch("src.api.routes.jobs.JobRepository.update_celery_task_id"), \
             patch("src.api.routes.jobs.JobRepository.update_status") as mock_update_status:

            mock_task.apply_async.return_value.id = "task-abc"
            mock_db.refresh = MagicMock()

            api_client.post("/api/v1/jobs/", json={"url": "https://example.com"})

            mock_update_status.assert_called_once()
            args = mock_update_status.call_args[0]
            assert args[2] == JobStatus.IN_PROGRESS.value


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{job_id}
# ---------------------------------------------------------------------------

class TestGetJobStatus:
    def test_returns_200_for_existing_job(self, api_client):
        mock_job = make_mock_job(status=JobStatus.COMPLETED.value)

        with patch("src.api.routes.jobs.JobRepository.get", return_value=mock_job):
            response = api_client.get(f"/api/v1/jobs/{mock_job.id}")

        assert response.status_code == 200

    def test_returns_404_for_missing_job(self, api_client):
        with patch("src.api.routes.jobs.JobRepository.get", return_value=None):
            response = api_client.get(f"/api/v1/jobs/{uuid4()}")

        assert response.status_code == 404

    def test_response_contains_status_field(self, api_client):
        mock_job = make_mock_job(status=JobStatus.IN_PROGRESS.value)

        with patch("src.api.routes.jobs.JobRepository.get", return_value=mock_job):
            response = api_client.get(f"/api/v1/jobs/{mock_job.id}")

        assert response.json()["status"] == JobStatus.IN_PROGRESS.value

    def test_response_contains_stats(self, api_client):
        mock_job = make_mock_job(
            total_pages_crawled=42,
            total_links_found=315,
            total_broken_links=5,
        )

        with patch("src.api.routes.jobs.JobRepository.get", return_value=mock_job):
            response = api_client.get(f"/api/v1/jobs/{mock_job.id}")

        body = response.json()
        assert body["total_pages_crawled"] == 42
        assert body["total_links_found"] == 315
        assert body["total_broken_links"] == 5


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/
# ---------------------------------------------------------------------------

class TestListJobs:
    def test_returns_200(self, api_client):
        mock_job = make_mock_job()

        with patch("src.api.routes.jobs.JobRepository.list_jobs", return_value=[mock_job]):
            response = api_client.get("/api/v1/jobs/")

        assert response.status_code == 200

    def test_response_has_total_and_jobs(self, api_client):
        mock_job = make_mock_job()

        with patch("src.api.routes.jobs.JobRepository.list_jobs", return_value=[mock_job]):
            response = api_client.get("/api/v1/jobs/")

        body = response.json()
        assert "total" in body
        assert "jobs" in body
        assert body["total"] == 1

    def test_empty_list(self, api_client):
        with patch("src.api.routes.jobs.JobRepository.list_jobs", return_value=[]):
            response = api_client.get("/api/v1/jobs/")

        assert response.json()["total"] == 0

    def test_passes_status_filter(self, api_client):
        with patch("src.api.routes.jobs.JobRepository.list_jobs", return_value=[]) as mock_list:
            api_client.get("/api/v1/jobs/?status=COMPLETED")
            mock_list.assert_called_once()
            kwargs = mock_list.call_args[1]
            assert kwargs.get("status") == "COMPLETED"


# ---------------------------------------------------------------------------
# DELETE /api/v1/jobs/{job_id}  (cancel)
# ---------------------------------------------------------------------------

class TestCancelJob:
    def test_cancel_pending_job_returns_200(self, api_client):
        mock_job = make_mock_job(status=JobStatus.PENDING.value)

        with patch("src.api.routes.jobs.JobRepository.get", return_value=mock_job), \
             patch("src.api.routes.jobs.JobRepository.update_status") as mock_update, \
             patch("src.api.routes.jobs.celery_app.control.revoke"):

            response = api_client.delete(f"/api/v1/jobs/{mock_job.id}")

        assert response.status_code == 200
        mock_update.assert_called_once()

    def test_cancel_completed_job_returns_400(self, api_client):
        mock_job = make_mock_job(status=JobStatus.COMPLETED.value)

        with patch("src.api.routes.jobs.JobRepository.get", return_value=mock_job):
            response = api_client.delete(f"/api/v1/jobs/{mock_job.id}")

        assert response.status_code == 400

    def test_cancel_failed_job_returns_400(self, api_client):
        mock_job = make_mock_job(status=JobStatus.FAILED.value)

        with patch("src.api.routes.jobs.JobRepository.get", return_value=mock_job):
            response = api_client.delete(f"/api/v1/jobs/{mock_job.id}")

        assert response.status_code == 400

    def test_cancel_already_cancelled_returns_400(self, api_client):
        mock_job = make_mock_job(status=JobStatus.CANCELLED.value)

        with patch("src.api.routes.jobs.JobRepository.get", return_value=mock_job):
            response = api_client.delete(f"/api/v1/jobs/{mock_job.id}")

        assert response.status_code == 400

    def test_cancel_missing_job_returns_404(self, api_client):
        with patch("src.api.routes.jobs.JobRepository.get", return_value=None):
            response = api_client.delete(f"/api/v1/jobs/{uuid4()}")

        assert response.status_code == 404

    def test_cancel_revokes_celery_task(self, api_client):
        mock_job = make_mock_job(status=JobStatus.IN_PROGRESS.value, celery_task_id="task-999")

        with patch("src.api.routes.jobs.JobRepository.get", return_value=mock_job), \
             patch("src.api.routes.jobs.JobRepository.update_status"), \
             patch("src.api.routes.jobs.celery_app.control.revoke") as mock_revoke:

            api_client.delete(f"/api/v1/jobs/{mock_job.id}")

            mock_revoke.assert_called_once_with("task-999", terminate=True, signal="SIGTERM")

    def test_cancel_sets_cancelled_status(self, api_client):
        mock_job = make_mock_job(status=JobStatus.IN_PROGRESS.value)

        with patch("src.api.routes.jobs.JobRepository.get", return_value=mock_job), \
             patch("src.api.routes.jobs.JobRepository.update_status") as mock_update, \
             patch("src.api.routes.jobs.celery_app.control.revoke"):

            api_client.delete(f"/api/v1/jobs/{mock_job.id}")

            args = mock_update.call_args[0]
            assert args[2] == JobStatus.CANCELLED.value


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self, api_client):
        response = api_client.get("/health/")
        assert response.status_code == 200

    def test_health_body(self, api_client):
        response = api_client.get("/health/")
        body = response.json()
        assert body["status"] == "healthy"
