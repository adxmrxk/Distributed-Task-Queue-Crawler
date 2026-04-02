from elasticsearch import Elasticsearch
from src.db.elasticsearch_client import get_es_client


def get_es() -> Elasticsearch:
    """FastAPI dependency — injects an Elasticsearch client into route handlers."""
    return get_es_client()
