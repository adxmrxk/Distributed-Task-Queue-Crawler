from celery import group
from confluent_kafka import Producer
import asyncio
import hashlib
import json
import redis
import logging

from src.worker.celery_app import app
from src.worker.base_task import BaseTaskWithRetry
from src.crawler.playwright_crawler import PlaywrightCrawler
from src.crawler.rate_limiter import DistributedRateLimiter
from src.crawler.politeness import PolitenessPolicy
from src.crawler.link_extractor import LinkExtractor
from src.db.elasticsearch_client import es_client
from src.db.repositories.job_repository import JobRepository
from src.db.repositories.link_repository import LinkRepository
from src.utils.url_utils import normalize_url, get_domain
from src.core.constants import JobStatus
from src.core.config import settings
from src.core.exceptions import RobotsTxtDeniedException, CrawlTimeoutException
from src.api.metrics import pages_crawled_total, crawl_duration_seconds

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
rate_limiter = DistributedRateLimiter()
politeness = PolitenessPolicy()

# Kafka producer — initialized lazily so import errors don't block the API
_kafka_producer = None

def get_kafka_producer():
    global _kafka_producer
    if _kafka_producer is None:
        _kafka_producer = Producer({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})
    return _kafka_producer


@app.task(base=BaseTaskWithRetry, bind=True, name='crawler.crawl_url')
def crawl_url(self, job_id: str, url: str, depth: int = 0):
    logger.info(f"Crawling URL at depth {depth}", extra={'job_id': job_id, 'url': url})

    try:
        job = JobRepository.get(es_client, job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            return {'error': 'Job not found'}

        if job['status'] == JobStatus.CANCELLED.value:
            return {'status': 'cancelled'}

        if depth > job['max_depth']:
            return {'status': 'max_depth_reached'}

        if job['total_pages_crawled'] >= job['max_pages']:
            return {'status': 'max_pages_reached'}

        # Deduplicate via Redis (fast) + ES (persistent)
        normalized = normalize_url(url)
        url_hash = hashlib.sha256(normalized.encode()).hexdigest()
        visited_key = f"visited:{job_id}:{url_hash}"

        if redis_client.exists(visited_key):
            return {'status': 'already_visited'}

        redis_client.setex(visited_key, 3600, "1")

        domain = get_domain(url)
        if not domain:
            return {'error': 'invalid_url'}

        if job.get('respect_robots_txt'):
            can_fetch = asyncio.run(politeness.can_fetch(url))
            if not can_fetch:
                raise RobotsTxtDeniedException(f"robots.txt denies: {url}")

        acquired = asyncio.run(rate_limiter.acquire(domain, tokens=1, max_wait=30.0))
        if not acquired:
            raise self.retry(countdown=10, max_retries=3)

        async def crawl():
            async with PlaywrightCrawler() as crawler:
                return await crawler.crawl_page(url)

        import time as _time
        _t0 = _time.monotonic()
        result = asyncio.run(crawl())
        crawl_duration_seconds.observe(_time.monotonic() - _t0)

        # Index the page into Elasticsearch (whether or not there was an error)
        LinkRepository.create_visited_url(
            es=es_client,
            job_id=job_id,
            url=url,
            normalized_url=normalized,
            title=result.get('title'),
            content=result.get('content'),
            depth=depth,
            status_code=result.get('status'),
            content_type=result.get('content_type'),
            links_count=len(result.get('links', [])),
        )

        if result['error']:
            logger.warning(f"Error crawling {url}: {result['error']}")
            return result

        JobRepository.increment_pages_crawled(es_client, job_id)
        JobRepository.increment_links_found(es_client, job_id, len(result['links']))
        pages_crawled_total.labels(job_id=job_id).inc()
        # Update last activity timestamp for completion detection
        import time
        redis_client.set(f"last_activity:{job_id}", str(time.time()), ex=3600)

        categorized = LinkExtractor.extract_links(
            base_url=url,
            links=result['links'],
            same_domain_only=False,
        )
        internal_links = categorized['internal']
        external_links = categorized['external']

        # BFS: spawn crawl tasks for internal links
        if internal_links and depth < job['max_depth']:
            links_to_crawl = internal_links[:100]
            if links_to_crawl:
                tasks = group(
                    crawl_url.s(job_id, link_url, depth + 1)
                    for link_url in links_to_crawl
                )
                tasks.apply_async()

        # Publish link-check job to Kafka — consumed by the Go link checker service.
        if external_links:
            payload = json.dumps({
                "job_id": job_id,
                "source_url": url,
                "target_urls": external_links,
                "depth": depth,
            }).encode("utf-8")
            producer = get_kafka_producer()
            producer.produce("link_check_jobs", value=payload, key=job_id.encode("utf-8"))
            producer.poll(0)

        # Schedule a completion check 30 seconds from now
        check_job_completion.apply_async(args=[job_id], countdown=30)

        return {
            'status': 'success',
            'url': url,
            'depth': depth,
            'internal_links': len(internal_links),
            'external_links': len(external_links),
        }

    except CrawlTimeoutException as e:
        raise self.retry(exc=e, countdown=_backoff(self.request.retries))

    except RobotsTxtDeniedException:
        return {'status': 'robots_denied', 'url': url}

    except Exception as e:
        logger.error(f"Error in crawl_url: {e}", extra={'job_id': job_id, 'url': url}, exc_info=True)
        raise


def _backoff(retry_count: int) -> int:
    from src.utils.retry_utils import calculate_exponential_backoff
    return calculate_exponential_backoff(retry_count)


@app.task(name='crawler.check_job_completion')
def check_job_completion(job_id: str):
    """Mark a job as completed if no new pages have been crawled in the last 30 seconds."""
    import time
    job = JobRepository.get(es_client, job_id)
    if not job or job['status'] != JobStatus.IN_PROGRESS.value:
        return

    last = redis_client.get(f"last_activity:{job_id}")
    if last and (time.time() - float(last)) < 30:
        # Still active — check again in 30 seconds
        check_job_completion.apply_async(args=[job_id], countdown=30)
        return

    # No activity for 30s — mark complete
    JobRepository.update_status(es_client, job_id, JobStatus.COMPLETED.value)
    redis_client.delete(f"last_activity:{job_id}")
    logger.info(f"Job {job_id} marked as completed")
