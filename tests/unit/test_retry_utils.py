"""Unit tests for src/utils/retry_utils.py"""
import pytest
from unittest.mock import patch
from src.utils.retry_utils import calculate_exponential_backoff, should_retry


class TestCalculateExponentialBackoff:
    def test_first_retry_uses_base_delay(self):
        # retry_count=0 → delay = base * 2^0 = base (before jitter)
        result = calculate_exponential_backoff(retry_count=0, base_delay=60, max_delay=600, jitter=False)
        assert result == 60

    def test_second_retry_doubles(self):
        result = calculate_exponential_backoff(retry_count=1, base_delay=60, max_delay=600, jitter=False)
        assert result == 120

    def test_third_retry(self):
        result = calculate_exponential_backoff(retry_count=2, base_delay=60, max_delay=600, jitter=False)
        assert result == 240

    def test_capped_at_max_delay(self):
        # With a large retry count the exponential would exceed max
        result = calculate_exponential_backoff(retry_count=10, base_delay=60, max_delay=600, jitter=False)
        assert result == 600

    def test_jitter_adds_positive_amount(self):
        # With jitter, result should be >= base delay (jitter is always non-negative)
        no_jitter = calculate_exponential_backoff(0, base_delay=60, max_delay=600, jitter=False)
        with_jitter = calculate_exponential_backoff(0, base_delay=60, max_delay=600, jitter=True)
        assert with_jitter >= no_jitter

    def test_jitter_within_10_percent(self):
        base_delay = 60
        results = [
            calculate_exponential_backoff(0, base_delay=base_delay, max_delay=600, jitter=True)
            for _ in range(20)
        ]
        for r in results:
            # Result should be between base and base * 1.1
            assert base_delay <= r <= base_delay * 1.1 + 1  # +1 for int rounding

    def test_returns_int(self):
        result = calculate_exponential_backoff(0, base_delay=60, max_delay=600, jitter=True)
        assert isinstance(result, int)

    def test_uses_settings_defaults_when_none(self):
        # Should not raise even when base_delay/max_delay are not provided
        result = calculate_exponential_backoff(0, jitter=False)
        assert result > 0

    def test_zero_retry_count(self):
        result = calculate_exponential_backoff(0, base_delay=10, max_delay=100, jitter=False)
        assert result == 10


class TestShouldRetry:
    def test_should_retry_when_under_max(self):
        should, delay = should_retry(retry_count=0, max_retries=5)
        assert should is True
        assert delay > 0

    def test_should_not_retry_at_max(self):
        should, delay = should_retry(retry_count=5, max_retries=5)
        assert should is False
        assert delay == 0

    def test_should_not_retry_above_max(self):
        should, delay = should_retry(retry_count=10, max_retries=5)
        assert should is False

    def test_delay_increases_with_retry_count(self):
        _, delay_first = should_retry(retry_count=0, max_retries=10)
        _, delay_later = should_retry(retry_count=3, max_retries=10)
        # Later retries should generally have larger delays
        assert delay_later >= delay_first

    def test_last_allowed_retry(self):
        should, delay = should_retry(retry_count=4, max_retries=5)
        assert should is True
        assert delay > 0

    def test_uses_settings_max_retries_when_none(self):
        # Should work without explicit max_retries
        should, delay = should_retry(retry_count=0)
        assert isinstance(should, bool)
