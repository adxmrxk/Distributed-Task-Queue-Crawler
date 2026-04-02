from elasticsearch import Elasticsearch, NotFoundError
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import logging

from src.db.indices import CRAWL_JOBS_INDEX
from src.db.elasticsearch_client import doc_to_dict
from src.core.constants import JobStatus

logger = logging.getLogger(__name__)


class JobRepository:

    @staticmethod
    def create(
        es: Elasticsearch,
        url: str,
        max_depth: int = 3,
        max_pages: int = 100,
        respect_robots_txt: bool = True,
        user_id: Optional[str] = None,
    ) -> dict:
        job_id = str(uuid.uuid4())
        doc = {
            "url": url,
            "status": JobStatus.PENDING.value,
            "max_depth": max_depth,
            "max_pages": max_pages,
            "respect_robots_txt": respect_robots_txt,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "total_pages_crawled": 0,
            "total_links_found": 0,
            "total_broken_links": 0,
            "celery_task_id": None,
            "error_message": None,
        }
        es.index(index=CRAWL_JOBS_INDEX, id=job_id, document=doc, refresh=True)
        doc["id"] = job_id
        return doc

    @staticmethod
    def get(es: Elasticsearch, job_id: str) -> Optional[dict]:
        try:
            hit = es.get(index=CRAWL_JOBS_INDEX, id=job_id)
            return doc_to_dict(hit)
        except NotFoundError:
            return None

    @staticmethod
    def list_jobs(
        es: Elasticsearch,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[dict]:
        must = []
        if status:
            must.append({"term": {"status": status}})
        if user_id:
            must.append({"term": {"user_id": user_id}})

        query = {"bool": {"must": must}} if must else {"match_all": {}}

        resp = es.search(
            index=CRAWL_JOBS_INDEX,
            query=query,
            sort=[{"created_at": {"order": "desc"}}],
            from_=skip,
            size=limit,
        )
        return [doc_to_dict(h) for h in resp["hits"]["hits"]]

    @staticmethod
    def update_status(
        es: Elasticsearch,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[dict]:
        now = datetime.now(timezone.utc).isoformat()
        update: dict = {"status": status}

        if status == JobStatus.IN_PROGRESS.value:
            # Only set started_at if not already set
            existing = JobRepository.get(es, job_id)
            if existing and not existing.get("started_at"):
                update["started_at"] = now
        elif status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value):
            update["completed_at"] = now

        if error_message:
            update["error_message"] = error_message

        try:
            es.update(index=CRAWL_JOBS_INDEX, id=job_id, doc=update, refresh=True)
            return JobRepository.get(es, job_id)
        except NotFoundError:
            return None

    @staticmethod
    def update_celery_task_id(es: Elasticsearch, job_id: str, celery_task_id: str) -> Optional[dict]:
        try:
            es.update(index=CRAWL_JOBS_INDEX, id=job_id, doc={"celery_task_id": celery_task_id}, refresh=True)
            return JobRepository.get(es, job_id)
        except NotFoundError:
            return None

    @staticmethod
    def increment_pages_crawled(es: Elasticsearch, job_id: str) -> None:
        es.update(
            index=CRAWL_JOBS_INDEX,
            id=job_id,
            script={"source": "ctx._source.total_pages_crawled += 1", "lang": "painless"},
        )

    @staticmethod
    def increment_links_found(es: Elasticsearch, job_id: str, count: int = 1) -> None:
        es.update(
            index=CRAWL_JOBS_INDEX,
            id=job_id,
            script={
                "source": "ctx._source.total_links_found += params.count",
                "lang": "painless",
                "params": {"count": count},
            },
        )

    @staticmethod
    def increment_broken_links(es: Elasticsearch, job_id: str) -> None:
        es.update(
            index=CRAWL_JOBS_INDEX,
            id=job_id,
            script={"source": "ctx._source.total_broken_links += 1", "lang": "painless"},
        )

    @staticmethod
    def delete(es: Elasticsearch, job_id: str) -> bool:
        try:
            es.delete(index=CRAWL_JOBS_INDEX, id=job_id, refresh=True)
            return True
        except NotFoundError:
            return False
