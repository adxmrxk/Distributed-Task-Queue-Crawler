"""
Elasticsearch index definitions and setup.
Run once on startup to ensure all indices exist with the correct mappings.
"""
from elasticsearch import Elasticsearch
import logging

logger = logging.getLogger(__name__)

CRAWL_JOBS_INDEX = "crawl_jobs"
BROKEN_LINKS_INDEX = "broken_links"
CRAWLED_PAGES_INDEX = "crawled_pages"
DLQ_INDEX = "dead_letter_queue"
RETRY_HISTORY_INDEX = "retry_history"

INDEX_MAPPINGS = {
    CRAWL_JOBS_INDEX: {
        "mappings": {
            "properties": {
                "url":                  {"type": "keyword"},
                "status":               {"type": "keyword"},
                "max_depth":            {"type": "integer"},
                "max_pages":            {"type": "integer"},
                "respect_robots_txt":   {"type": "boolean"},
                "created_at":           {"type": "date"},
                "started_at":           {"type": "date"},
                "completed_at":         {"type": "date"},
                "total_pages_crawled":  {"type": "integer"},
                "total_links_found":    {"type": "integer"},
                "total_broken_links":   {"type": "integer"},
                "celery_task_id":       {"type": "keyword"},
                "user_id":              {"type": "keyword"},
                "error_message":        {"type": "text"},
            }
        }
    },
    BROKEN_LINKS_INDEX: {
        "mappings": {
            "properties": {
                "job_id":        {"type": "keyword"},
                "source_url":    {"type": "keyword"},
                "broken_url":    {"type": "keyword"},
                "anchor_text":   {"type": "text"},
                "status_code":   {"type": "integer"},
                "error_type":    {"type": "keyword"},
                "error_message": {"type": "text"},
                "depth":         {"type": "integer"},
                "discovered_at": {"type": "date"},
            }
        }
    },
    CRAWLED_PAGES_INDEX: {
        "mappings": {
            "properties": {
                "job_id":        {"type": "keyword"},
                "url":           {"type": "keyword"},
                "normalized_url":{"type": "keyword"},
                "title":         {"type": "text", "analyzer": "english"},
                "content":       {"type": "text", "analyzer": "english"},
                "depth":         {"type": "integer"},
                "status_code":   {"type": "integer"},
                "content_type":  {"type": "keyword"},
                "links_count":   {"type": "integer"},
                "crawled_at":    {"type": "date"},
            }
        }
    },
    DLQ_INDEX: {
        "mappings": {
            "properties": {
                "job_id":            {"type": "keyword"},
                "celery_task_id":    {"type": "keyword"},
                "task_name":         {"type": "keyword"},
                "exception_class":   {"type": "keyword"},
                "exception_message": {"type": "text"},
                "traceback":         {"type": "text"},
                "total_retries":     {"type": "integer"},
                "acknowledged":      {"type": "boolean"},
                "final_failure_at":  {"type": "date"},
            }
        }
    },
    RETRY_HISTORY_INDEX: {
        "mappings": {
            "properties": {
                "celery_task_id":    {"type": "keyword"},
                "retry_number":      {"type": "integer"},
                "exception_class":   {"type": "keyword"},
                "exception_message": {"type": "text"},
                "backoff_seconds":   {"type": "integer"},
                "retried_at":        {"type": "date"},
            }
        }
    },
}


def create_indices(es: Elasticsearch) -> None:
    """Create all indices if they don't already exist."""
    for index_name, body in INDEX_MAPPINGS.items():
        if not es.indices.exists(index=index_name):
            es.indices.create(index=index_name, body=body)
            logger.info(f"Created Elasticsearch index: {index_name}")
        else:
            logger.debug(f"Elasticsearch index already exists: {index_name}")
