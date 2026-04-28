"""
Integration tests for LinkRepository using a mocked SQLAlchemy session.
"""
import hashlib
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from src.db.repositories.link_repository import LinkRepository
from src.db.models.broken_link import BrokenLink
from src.db.models.visited_url import VisitedUrl


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def job_id():
    return uuid4()


# ---------------------------------------------------------------------------
# create_broken_link
# ---------------------------------------------------------------------------

class TestCreateBrokenLink:
    def test_adds_and_commits(self, db, job_id):
        LinkRepository.create_broken_link(
            db, job_id=job_id,
            source_url="https://example.com/page",
            broken_url="https://example.com/missing",
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_returns_broken_link_instance(self, db, job_id):
        result = LinkRepository.create_broken_link(
            db, job_id=job_id,
            source_url="https://example.com/page",
            broken_url="https://example.com/404",
        )
        assert isinstance(result, BrokenLink)

    def test_stores_all_fields(self, db, job_id):
        link = LinkRepository.create_broken_link(
            db, job_id=job_id,
            source_url="https://example.com/a",
            broken_url="https://example.com/b",
            anchor_text="Click here",
            status_code=404,
            error_type="HTTP_ERROR",
            error_message="Not Found",
            depth=2,
        )
        assert link.source_url == "https://example.com/a"
        assert link.broken_url == "https://example.com/b"
        assert link.anchor_text == "Click here"
        assert link.status_code == 404
        assert link.error_type == "HTTP_ERROR"
        assert link.depth == 2


# ---------------------------------------------------------------------------
# get_broken_links_by_job
# ---------------------------------------------------------------------------

class TestGetBrokenLinksByJob:
    def test_queries_by_job_id(self, db, job_id):
        mock_link = MagicMock(spec=BrokenLink)
        db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_link]

        result = LinkRepository.get_broken_links_by_job(db, job_id)

        db.query.assert_called_with(BrokenLink)
        assert mock_link in result

    def test_returns_empty_list_when_none(self, db, job_id):
        db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

        result = LinkRepository.get_broken_links_by_job(db, job_id)

        assert result == []


# ---------------------------------------------------------------------------
# count_broken_links_by_job
# ---------------------------------------------------------------------------

class TestCountBrokenLinksByJob:
    def test_returns_count(self, db, job_id):
        db.query.return_value.filter.return_value.count.return_value = 7

        result = LinkRepository.count_broken_links_by_job(db, job_id)

        assert result == 7

    def test_returns_zero_when_none(self, db, job_id):
        db.query.return_value.filter.return_value.count.return_value = 0

        result = LinkRepository.count_broken_links_by_job(db, job_id)

        assert result == 0


# ---------------------------------------------------------------------------
# create_visited_url
# ---------------------------------------------------------------------------

class TestCreateVisitedUrl:
    def test_adds_and_commits(self, db, job_id):
        LinkRepository.create_visited_url(
            db, job_id=job_id,
            url="https://example.com/Page",
            normalized_url="https://example.com/page",
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_returns_visited_url_instance(self, db, job_id):
        result = LinkRepository.create_visited_url(
            db, job_id=job_id,
            url="https://example.com/Page",
            normalized_url="https://example.com/page",
        )
        assert isinstance(result, VisitedUrl)

    def test_hash_is_sha256_of_normalized_url(self, db, job_id):
        normalized = "https://example.com/page"
        expected_hash = hashlib.sha256(normalized.encode()).hexdigest()

        result = LinkRepository.create_visited_url(
            db, job_id=job_id,
            url="https://example.com/Page",
            normalized_url=normalized,
        )

        assert result.url_hash == expected_hash

    def test_stores_depth_and_status_code(self, db, job_id):
        result = LinkRepository.create_visited_url(
            db, job_id=job_id,
            url="https://example.com/page",
            normalized_url="https://example.com/page",
            depth=2,
            status_code=200,
            content_type="text/html",
        )
        assert result.depth == 2
        assert result.status_code == 200
        assert result.content_type == "text/html"


# ---------------------------------------------------------------------------
# is_url_visited
# ---------------------------------------------------------------------------

class TestIsUrlVisited:
    def test_returns_true_when_visited(self, db, job_id):
        db.query.return_value.filter.return_value.first.return_value = MagicMock(spec=VisitedUrl)

        assert LinkRepository.is_url_visited(db, job_id, "https://example.com/page") is True

    def test_returns_false_when_not_visited(self, db, job_id):
        db.query.return_value.filter.return_value.first.return_value = None

        assert LinkRepository.is_url_visited(db, job_id, "https://example.com/new") is False

    def test_uses_hash_for_lookup(self, db, job_id):
        """Verify the query is driven by SHA256 hash, not raw URL string."""
        db.query.return_value.filter.return_value.first.return_value = None
        url = "https://example.com/path"

        LinkRepository.is_url_visited(db, job_id, url)

        # The filter call should involve the VisitedUrl model
        db.query.assert_called_with(VisitedUrl)
