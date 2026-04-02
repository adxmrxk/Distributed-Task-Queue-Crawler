from elasticsearch import Elasticsearch
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_es_client() -> Elasticsearch:
    return Elasticsearch(settings.ELASTICSEARCH_URL)


# Singleton used by Celery tasks (synchronous context)
es_client = get_es_client()


def doc_to_dict(hit: dict) -> dict:
    """Convert an ES hit (_source + _id) into a flat dict the API can return."""
    doc = hit["_source"].copy()
    doc["id"] = hit["_id"]
    return doc
