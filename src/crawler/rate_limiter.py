import redis
import time
import asyncio
from typing import Optional
import logging
from src.core.config import settings

logger = logging.getLogger(__name__)


class DistributedRateLimiter:
    """
    Redis-backed distributed rate limiter using token bucket algorithm

    Ensures that multiple workers respect per-domain rate limits
    """

    def __init__(
        self,
        redis_url: str = None,
        rate: float = None,
        capacity: int = None
    ):
        """
        Initialize rate limiter

        Args:
            redis_url: Redis connection URL (default from settings)
            rate: Tokens per second (default from settings)
            capacity: Maximum burst capacity (default 5)
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client = redis.from_url(
            self.redis_url,
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS
        )
        self.rate = rate or settings.CRAWLER_RATE_LIMIT_PER_DOMAIN
        self.capacity = capacity or 5  # Burst capacity

        # Lua script for atomic token bucket operations
        self.lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local capacity = tonumber(ARGV[3])
        local requested = tonumber(ARGV[4])

        -- Get current bucket state
        local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
        local tokens = tonumber(bucket[1]) or capacity
        local last_update = tonumber(bucket[2]) or now

        -- Add tokens based on time elapsed
        local delta = math.max(0, now - last_update)
        tokens = math.min(capacity, tokens + delta * rate)

        -- Check if we have enough tokens
        if tokens >= requested then
            tokens = tokens - requested
            redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
            redis.call('EXPIRE', key, 3600)
            return 1
        else
            -- Return time to wait for token refill
            local tokens_needed = requested - tokens
            local wait_time = tokens_needed / rate
            return -1 * wait_time
        end
        """

        self.script_sha = None
        try:
            self.script_sha = self.redis_client.script_load(self.lua_script)
        except Exception as e:
            logger.warning(f"Failed to preload Lua script: {e}")

    async def acquire(
        self,
        domain: str,
        tokens: int = 1,
        max_wait: float = 30.0
    ) -> bool:
        """
        Acquire tokens for a domain (async wrapper)

        Args:
            domain: Domain to rate limit
            tokens: Number of tokens to acquire
            max_wait: Maximum time to wait in seconds

        Returns:
            True if tokens acquired, False if timeout
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._acquire_sync,
            domain,
            tokens,
            max_wait
        )

    def _acquire_sync(
        self,
        domain: str,
        tokens: int = 1,
        max_wait: float = 30.0
    ) -> bool:
        """
        Synchronous token acquisition with retry

        Args:
            domain: Domain to rate limit
            tokens: Number of tokens to acquire
            max_wait: Maximum time to wait in seconds

        Returns:
            True if tokens acquired, False if timeout
        """
        key = f"rate_limit:{domain}"
        start_time = time.time()

        while True:
            now = time.time()
            elapsed = now - start_time

            if elapsed > max_wait:
                logger.warning(
                    f"Rate limit timeout for {domain} after {elapsed:.2f}s",
                    extra={'domain': domain, 'elapsed': elapsed}
                )
                return False

            try:
                # Execute Lua script
                if self.script_sha:
                    try:
                        result = self.redis_client.evalsha(
                            self.script_sha,
                            1,
                            key,
                            now,
                            self.rate,
                            self.capacity,
                            tokens
                        )
                    except redis.exceptions.NoScriptError:
                        # Script not cached, reload it
                        self.script_sha = self.redis_client.script_load(self.lua_script)
                        result = self.redis_client.evalsha(
                            self.script_sha,
                            1,
                            key,
                            now,
                            self.rate,
                            self.capacity,
                            tokens
                        )
                else:
                    # Fallback: execute script directly
                    result = self.redis_client.eval(
                        self.lua_script,
                        1,
                        key,
                        now,
                        self.rate,
                        self.capacity,
                        tokens
                    )

                if result == 1:
                    # Tokens acquired
                    logger.debug(
                        f"Rate limit acquired for {domain}",
                        extra={'domain': domain}
                    )
                    return True
                else:
                    # Need to wait
                    wait_time = abs(float(result))
                    # Cap wait time to avoid excessive delays
                    wait_time = min(wait_time, 5.0)

                    if elapsed + wait_time > max_wait:
                        logger.warning(f"Would exceed max wait time for {domain}")
                        return False

                    logger.debug(
                        f"Rate limited, waiting {wait_time:.2f}s for {domain}",
                        extra={'domain': domain, 'wait_time': wait_time}
                    )
                    time.sleep(wait_time)

            except redis.exceptions.RedisError as e:
                logger.error(f"Redis error in rate limiter: {e}")
                # On Redis error, allow the request (fail open)
                return True
            except Exception as e:
                logger.error(f"Unexpected error in rate limiter: {e}")
                return True

    def reset(self, domain: str):
        """Reset rate limit for a domain"""
        key = f"rate_limit:{domain}"
        try:
            self.redis_client.delete(key)
            logger.info(f"Reset rate limit for {domain}")
        except Exception as e:
            logger.error(f"Failed to reset rate limit for {domain}: {e}")

    def get_status(self, domain: str) -> Optional[dict]:
        """Get current rate limit status for a domain"""
        key = f"rate_limit:{domain}"
        try:
            bucket = self.redis_client.hmget(key, 'tokens', 'last_update')
            if bucket[0] is not None:
                return {
                    'domain': domain,
                    'tokens': float(bucket[0]),
                    'last_update': float(bucket[1]) if bucket[1] else None,
                    'capacity': self.capacity,
                    'rate': self.rate
                }
        except Exception as e:
            logger.error(f"Failed to get rate limit status for {domain}: {e}")
        return None
