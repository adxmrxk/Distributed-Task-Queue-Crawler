import random
from typing import Tuple
from src.core.config import settings


def calculate_exponential_backoff(
    retry_count: int,
    base_delay: int = None,
    max_delay: int = None,
    jitter: bool = True
) -> int:
    """
    Calculate exponential backoff delay with optional jitter

    Args:
        retry_count: Current retry attempt number (0-indexed)
        base_delay: Base delay in seconds (default from settings)
        max_delay: Maximum delay cap in seconds (default from settings)
        jitter: Whether to add random jitter (default True)

    Returns:
        Delay in seconds before next retry
    """
    if base_delay is None:
        base_delay = settings.RETRY_BACKOFF_BASE
    if max_delay is None:
        max_delay = settings.RETRY_BACKOFF_MAX

    # Calculate exponential delay: base * 2^retry_count
    delay = min(base_delay * (2 ** retry_count), max_delay)

    # Add jitter to prevent thundering herd
    if jitter:
        jitter_amount = random.uniform(0, delay * 0.1)  # ±10% jitter
        delay = delay + jitter_amount

    return int(delay)


def should_retry(
    retry_count: int,
    max_retries: int = None
) -> Tuple[bool, int]:
    """
    Determine if a task should be retried and calculate the next delay

    Args:
        retry_count: Current retry attempt number
        max_retries: Maximum retry attempts (default from settings)

    Returns:
        Tuple of (should_retry: bool, delay_seconds: int)
    """
    if max_retries is None:
        max_retries = settings.RETRY_MAX_ATTEMPTS

    if retry_count >= max_retries:
        return False, 0

    delay = calculate_exponential_backoff(retry_count)
    return True, delay
