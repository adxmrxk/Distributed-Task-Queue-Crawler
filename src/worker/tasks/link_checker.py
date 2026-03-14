import asyncio
from uuid import UUID
import logging
from typing import List
from src.worker.celery_app import app
from src.worker.base_task import BaseTaskWithRetry
from src.crawler.link_validator import LinkValidator
from src.db.session import get_db_session
from src.db.repositories.job_repository import JobRepository
from src.db.repositories.link_repository import LinkRepository

logger = logging.getLogger(__name__)


@app.task(base=BaseTaskWithRetry, bind=True, name='link_checker.check_link')
def check_link(self, job_id: str, source_url: str, target_url: str, anchor_text: str, depth: int):
    """
    Check if a single link is broken

    Args:
        job_id: UUID of the crawl job
        source_url: URL of the page containing the link
        target_url: URL to check
        anchor_text: Anchor text of the link
        depth: Depth where link was discovered

    Returns:
        Dictionary with validation result
    """
    logger.debug(
        f"Checking link: {target_url}",
        extra={'job_id': job_id, 'source_url': source_url, 'target_url': target_url}
    )

    try:
        # Validate the link
        validator = LinkValidator()
        is_valid, status_code, error_type, error_message = asyncio.run(
            validator.check_link(target_url)
        )

        # If broken, store in database
        if not is_valid:
            logger.info(
                f"Broken link found: {target_url} (status: {status_code}, error: {error_type})",
                extra={
                    'job_id': job_id,
                    'source_url': source_url,
                    'target_url': target_url,
                    'status_code': status_code,
                    'error_type': error_type
                }
            )

            with get_db_session() as db:
                # Create broken link record
                LinkRepository.create_broken_link(
                    db=db,
                    job_id=UUID(job_id),
                    source_url=source_url,
                    broken_url=target_url,
                    anchor_text=anchor_text[:500] if anchor_text else None,  # Limit length
                    status_code=status_code,
                    error_type=error_type,
                    error_message=error_message[:1000] if error_message else None,  # Limit length
                    depth=depth
                )

                # Update job statistics
                JobRepository.increment_broken_links(db, UUID(job_id))

            return {
                'status': 'broken',
                'target_url': target_url,
                'status_code': status_code,
                'error_type': error_type
            }
        else:
            logger.debug(f"Link valid: {target_url} (status {status_code})")
            return {
                'status': 'valid',
                'target_url': target_url,
                'status_code': status_code
            }

    except Exception as e:
        logger.error(
            f"Error checking link {target_url}: {str(e)}",
            extra={'job_id': job_id, 'target_url': target_url},
            exc_info=True
        )
        raise


@app.task(base=BaseTaskWithRetry, bind=True, name='link_checker.check_links_batch')
def check_links_batch(
    self,
    job_id: str,
    source_url: str,
    target_urls: List[str],
    depth: int,
    batch_size: int = 50
):
    """
    Check multiple links in batches for efficiency

    Args:
        job_id: UUID of the crawl job
        source_url: URL of the page containing the links
        target_urls: List of URLs to check
        depth: Depth where links were discovered
        batch_size: Number of links to check concurrently

    Returns:
        Dictionary with batch results
    """
    logger.info(
        f"Checking batch of {len(target_urls)} links",
        extra={'job_id': job_id, 'source_url': source_url, 'count': len(target_urls)}
    )

    try:
        validator = LinkValidator()

        # Check links in batches
        broken_count = 0
        valid_count = 0

        for i in range(0, len(target_urls), batch_size):
            batch = target_urls[i:i + batch_size]

            # Check batch concurrently
            results = asyncio.run(
                validator.check_multiple_links(batch, max_concurrent=10)
            )

            # Process results
            with get_db_session() as db:
                for target_url, (is_valid, status_code, error_type, error_message) in results.items():
                    if not is_valid:
                        # Store broken link
                        LinkRepository.create_broken_link(
                            db=db,
                            job_id=UUID(job_id),
                            source_url=source_url,
                            broken_url=target_url,
                            anchor_text=None,  # Not available in batch mode
                            status_code=status_code,
                            error_type=error_type,
                            error_message=error_message[:1000] if error_message else None,
                            depth=depth
                        )
                        broken_count += 1
                    else:
                        valid_count += 1

                # Update job statistics (batch update)
                if broken_count > 0:
                    for _ in range(broken_count):
                        JobRepository.increment_broken_links(db, UUID(job_id))

        logger.info(
            f"Batch check complete: {valid_count} valid, {broken_count} broken",
            extra={
                'job_id': job_id,
                'valid_count': valid_count,
                'broken_count': broken_count
            }
        )

        return {
            'status': 'complete',
            'total_checked': len(target_urls),
            'valid_count': valid_count,
            'broken_count': broken_count
        }

    except Exception as e:
        logger.error(
            f"Error in batch link check: {str(e)}",
            extra={'job_id': job_id, 'source_url': source_url},
            exc_info=True
        )
        raise
