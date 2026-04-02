"""
Search across crawled page content stored in Elasticsearch.
This is the core value-add over the old PostgreSQL setup.
"""
from elasticsearch import Elasticsearch
from typing import Optional, List
import logging

from src.db.indices import CRAWLED_PAGES_INDEX
from src.db.elasticsearch_client import doc_to_dict

logger = logging.getLogger(__name__)


class PageRepository:

    @staticmethod
    def search(
        es: Elasticsearch,
        query: str,
        job_id: Optional[str] = None,
        size: int = 20,
    ) -> List[dict]:
        """
        Full-text search across all indexed page content.

        Searches title (boosted 3x) and body content. Optionally scoped
        to a single crawl job.
        """
        must = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        ]
        if job_id:
            must.append({"term": {"job_id": job_id}})

        resp = es.search(
            index=CRAWLED_PAGES_INDEX,
            query={"bool": {"must": must}},
            highlight={
                "fields": {
                    "title": {},
                    "content": {"fragment_size": 200, "number_of_fragments": 2},
                }
            },
            source=["job_id", "url", "title", "depth", "status_code", "crawled_at"],
            size=size,
        )

        results = []
        for hit in resp["hits"]["hits"]:
            doc = doc_to_dict(hit)
            doc["score"] = hit["_score"]
            doc["highlights"] = hit.get("highlight", {})
            results.append(doc)

        return results

    @staticmethod
    def get_pages_by_job(
        es: Elasticsearch,
        job_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[dict]:
        resp = es.search(
            index=CRAWLED_PAGES_INDEX,
            query={"term": {"job_id": job_id}},
            sort=[{"crawled_at": {"order": "desc"}}],
            from_=skip,
            size=limit,
        )
        return [doc_to_dict(h) for h in resp["hits"]["hits"]]
