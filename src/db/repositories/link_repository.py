from elasticsearch import Elasticsearch
from typing import Optional, List
from datetime import datetime, timezone
import hashlib
import uuid
import logging

from src.db.indices import BROKEN_LINKS_INDEX, CRAWLED_PAGES_INDEX
from src.db.elasticsearch_client import doc_to_dict

logger = logging.getLogger(__name__)


class LinkRepository:

    # ------------------------------------------------------------------
    # Broken links
    # ------------------------------------------------------------------

    @staticmethod
    def create_broken_link(
        es: Elasticsearch,
        job_id: str,
        source_url: str,
        broken_url: str,
        anchor_text: Optional[str] = None,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        depth: Optional[int] = None,
    ) -> dict:
        doc = {
            "job_id": job_id,
            "source_url": source_url,
            "broken_url": broken_url,
            "anchor_text": anchor_text,
            "status_code": status_code,
            "error_type": error_type,
            "error_message": error_message,
            "depth": depth,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        }
        doc_id = str(uuid.uuid4())
        es.index(index=BROKEN_LINKS_INDEX, id=doc_id, document=doc, refresh=True)
        doc["id"] = doc_id
        return doc

    @staticmethod
    def get_broken_links_by_job(
        es: Elasticsearch,
        job_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[dict]:
        resp = es.search(
            index=BROKEN_LINKS_INDEX,
            query={"term": {"job_id": job_id}},
            sort=[{"discovered_at": {"order": "desc"}}],
            from_=skip,
            size=limit,
        )
        return [doc_to_dict(h) for h in resp["hits"]["hits"]]

    @staticmethod
    def count_broken_links_by_job(es: Elasticsearch, job_id: str) -> int:
        resp = es.count(index=BROKEN_LINKS_INDEX, query={"term": {"job_id": job_id}})
        return resp["count"]

    # ------------------------------------------------------------------
    # Visited / crawled pages
    # ------------------------------------------------------------------

    @staticmethod
    def create_visited_url(
        es: Elasticsearch,
        job_id: str,
        url: str,
        normalized_url: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        depth: Optional[int] = None,
        status_code: Optional[int] = None,
        content_type: Optional[str] = None,
        links_count: int = 0,
    ) -> dict:
        url_hash = hashlib.sha256(normalized_url.encode()).hexdigest()
        doc = {
            "job_id": job_id,
            "url": url,
            "normalized_url": normalized_url,
            "url_hash": url_hash,
            "title": title,
            "content": content,
            "depth": depth,
            "status_code": status_code,
            "content_type": content_type,
            "links_count": links_count,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }
        # Use url_hash as doc ID so re-visiting the same URL within a job is idempotent
        doc_id = f"{job_id}:{url_hash}"
        es.index(index=CRAWLED_PAGES_INDEX, id=doc_id, document=doc, refresh=True)
        doc["id"] = doc_id
        return doc

    @staticmethod
    def is_url_visited(es: Elasticsearch, job_id: str, normalized_url: str) -> bool:
        url_hash = hashlib.sha256(normalized_url.encode()).hexdigest()
        doc_id = f"{job_id}:{url_hash}"
        return es.exists(index=CRAWLED_PAGES_INDEX, id=doc_id)
