from celery import group
import asyncio
import hashlib
import redis
from uuid import UUID
import logging
from src.worker.celery_app import app
from src.worker.base_task import BaseTaskWithRetry
from src.crawler.playwright_crawler import PlaywrightCrawler
from src.crawler.rate_limiter import DistributedRateLimiter
from src.crawler.politeness import PolitenessPolicy
from src.crawler.link_extractor import LinkExtractor
from src.db.session import get_db_session
from src.db.repositories.job_repository import JobRepository
from src.db.repositories.link_repository import LinkRepository
from src.utils.url_utils import normalize_url, get_domain
from src.core.constants import JobStatus
from src.core.config import settings
from src.core.exceptions import RobotsTxtDeniedException, CrawlTimeoutException

logger = logging.getLogger(__name__)

# Initialize Redis client for visited URL tracking
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Initialize rate limiter and politeness policy
rate_limiter = DistributedRateLimiter()
politeness = PolitenessPolicy()


@app.task(base=BaseTaskWithRetry, bind=True, name='crawler.crawl_url')
def crawl_url(self, job_id: str, url: str, depth: int = 0):
    """
    Crawl a single URL and spawn tasks for discovered links (BFS)

    Args:
        job_id: UUID of the crawl job
        url: URL to crawl
        depth: Current depth in the crawl tree

    Returns:
        Dictionary with crawl results
    """
    logger.info(
        f"Crawling URL at depth {depth}",
        extra={'job_id': job_id, 'url': url, 'depth': depth}
    )

    try:
        # Get job from database
        with get_db_session() as db:
            job = JobRepository.get(db, UUID(job_id))

            if not job:
                logger.error(f"Job not found: {job_id}")
                return {'error': 'Job not found'}

            # Check if job was cancelled
            if job.status == JobStatus.CANCELLED.value:
                logger.info(f"Job cancelled, stopping crawl: {job_id}")
                return {'status': 'cancelled'}

            # Check depth limit
            if depth > job.max_depth:
                logger.debug(f"Max depth reached for {url}")
                return {'status': 'max_depth_reached'}

            # Check page limit
            if job.total_pages_crawled >= job.max_pages:
                logger.info(f"Max pages reached for job {job_id}")
                return {'status': 'max_pages_reached'}

        # Check if URL already visited (Redis for fast lookup)
        normalized = normalize_url(url)
        url_hash = hashlib.sha256(normalized.encode()).hexdigest()
        visited_key = f"visited:{job_id}:{url_hash}"

        if redis_client.exists(visited_key):
            logger.debug(f"URL already visited: {url}")
            return {'status': 'already_visited'}

        # Mark as visiting (prevent duplicate concurrent crawls)
        redis_client.setex(visited_key, 3600, "1")  # 1 hour TTL

        # Get domain for rate limiting
        domain = get_domain(url)
        if not domain:
            logger.warning(f"Could not extract domain from {url}")
            return {'error': 'invalid_url'}

        # Check robots.txt if enabled
        if job.respect_robots_txt:
            can_fetch = asyncio.run(politeness.can_fetch(url))
            if not can_fetch:
                logger.info(f"robots.txt denies access to {url}")
                raise RobotsTxtDeniedException(f"robots.txt denies: {url}")

        # Acquire rate limit token
        acquired = asyncio.run(rate_limiter.acquire(domain, tokens=1, max_wait=30.0))
        if not acquired:
            logger.warning(f"Failed to acquire rate limit for {domain}")
            # Retry later
            raise self.retry(countdown=10, max_retries=3)

        # Crawl the page with Playwright
        async def crawl():
            async with PlaywrightCrawler() as crawler:
                return await crawler.crawl_page(url)

        result = asyncio.run(crawl())

        if result['error']:
            logger.warning(
                f"Error crawling {url}: {result['error']}",
                extra={'url': url, 'error': result['error']}
            )
            # Store visited URL even if failed
            with get_db_session() as db:
                LinkRepository.create_visited_url(
                    db=db,
                    job_id=UUID(job_id),
                    url=url,
                    normalized_url=normalized,
                    depth=depth,
                    status_code=result.get('status'),
                    content_type=result.get('content_type')
                )
            return result

        # Store visited URL in database
        with get_db_session() as db:
            LinkRepository.create_visited_url(
                db=db,
                job_id=UUID(job_id),
                url=url,
                normalized_url=normalized,
                depth=depth,
                status_code=result['status'],
                content_type=result.get('content_type')
            )

            # Update job statistics
            JobRepository.increment_pages_crawled(db, UUID(job_id))
            JobRepository.increment_links_found(db, UUID(job_id), len(result['links']))

        # Extract and categorize links
        categorized = LinkExtractor.extract_links(
            base_url=url,
            links=result['links'],
            same_domain_only=False
        )

        internal_links = categorized['internal']
        external_links = categorized['external']

        logger.info(
            f"Extracted links from {url}: {len(internal_links)} internal, {len(external_links)} external",
            extra={
                'url': url,
                'internal_count': len(internal_links),
                'external_count': len(external_links)
            }
        )

        # Spawn tasks for internal links (crawl further) - BFS pattern
        if internal_links and depth < job.max_depth:
            # Limit fan-out to prevent queue explosion
            links_to_crawl = internal_links[:100]

            tasks = group(
                crawl_url.s(job_id, link_url, depth + 1)
                for link_url in links_to_crawl
            )
            tasks.apply_async()

            logger.debug(f"Spawned {len(links_to_crawl)} crawl tasks for next depth level")

        # Spawn link checking tasks for external links
        if external_links:
            from src.worker.tasks.link_checker import check_links_batch

            # Batch external links for efficient checking
            check_links_batch.apply_async(
                args=[job_id, url, external_links, depth],
                queue='link_checker'
            )

            logger.debug(f"Spawned batch link check for {len(external_links)} external links")

        return {
            'status': 'success',
            'url': url,
            'depth': depth,
            'internal_links': len(internal_links),
            'external_links': len(external_links),
            'http_status': result['status']
        }

    except CrawlTimeoutException as e:
        logger.warning(f"Timeout crawling {url}: {str(e)}")
        raise self.retry(exc=e, countdown=calculate_countdown(self.request.retries))

    except RobotsTxtDeniedException:
        # Don't retry robots.txt denials
        return {'status': 'robots_denied', 'url': url}

    except Exception as e:
        logger.error(
            f"Error in crawl_url task: {str(e)}",
            extra={'job_id': job_id, 'url': url, 'depth': depth},
            exc_info=True
        )
        raise


def calculate_countdown(retry_count: int) -> int:
    """Calculate exponential backoff countdown"""
    from src.utils.retry_utils import calculate_exponential_backoff
    return calculate_exponential_backoff(retry_count)
