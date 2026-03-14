import urllib.robotparser
from urllib.parse import urlparse
import aiohttp
import asyncio
from cachetools import TTLCache
from typing import Optional
import logging
from src.core.config import settings

logger = logging.getLogger(__name__)


class PolitenessPolicy:
    """
    Enforce politeness policies for web crawling

    - Respects robots.txt
    - Extracts and honors crawl-delay directive
    - Caches robots.txt for performance
    """

    def __init__(self, user_agent: str = None, cache_ttl: int = 3600):
        """
        Initialize politeness policy

        Args:
            user_agent: User agent string (default from settings)
            cache_ttl: Cache TTL in seconds (default 1 hour)
        """
        self.user_agent = user_agent or settings.CRAWLER_USER_AGENT
        self.robots_cache = TTLCache(maxsize=1000, ttl=cache_ttl)
        self.cache_lock = asyncio.Lock()

    async def can_fetch(self, url: str) -> bool:
        """
        Check if URL can be fetched according to robots.txt

        Args:
            url: URL to check

        Returns:
            True if allowed, False if denied
        """
        if not settings.CRAWLER_RESPECT_ROBOTS:
            return True

        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            # Get robots parser (from cache or fetch)
            rp = await self._get_robots_parser(robots_url)

            if rp is None:
                # If robots.txt fetch failed, allow crawling (fail open)
                logger.debug(f"No robots.txt for {parsed.netloc}, allowing crawl")
                return True

            can_fetch = rp.can_fetch(self.user_agent, url)

            if not can_fetch:
                logger.info(
                    f"robots.txt denies access to {url}",
                    extra={'url': url, 'robots_url': robots_url}
                )

            return can_fetch

        except Exception as e:
            logger.error(f"Error checking robots.txt for {url}: {e}")
            # On error, allow crawling (fail open)
            return True

    async def get_crawl_delay(self, url: str) -> float:
        """
        Get crawl delay from robots.txt

        Args:
            url: URL to check

        Returns:
            Crawl delay in seconds (default 1.0)
        """
        if not settings.CRAWLER_RESPECT_ROBOTS:
            return settings.CRAWLER_RATE_LIMIT_PER_DOMAIN

        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            rp = await self._get_robots_parser(robots_url)

            if rp is None:
                return settings.CRAWLER_RATE_LIMIT_PER_DOMAIN

            # Get crawl delay for our user agent
            delay = rp.crawl_delay(self.user_agent)

            if delay:
                logger.debug(
                    f"Crawl delay for {parsed.netloc}: {delay}s",
                    extra={'domain': parsed.netloc, 'delay': delay}
                )
                return float(delay)

            # Default to configured rate limit
            return settings.CRAWLER_RATE_LIMIT_PER_DOMAIN

        except Exception as e:
            logger.error(f"Error getting crawl delay for {url}: {e}")
            return settings.CRAWLER_RATE_LIMIT_PER_DOMAIN

    async def _get_robots_parser(
        self,
        robots_url: str
    ) -> Optional[urllib.robotparser.RobotFileParser]:
        """
        Get robots.txt parser (from cache or fetch)

        Args:
            robots_url: robots.txt URL

        Returns:
            RobotFileParser instance or None
        """
        # Check cache
        async with self.cache_lock:
            if robots_url in self.robots_cache:
                return self.robots_cache[robots_url]

        # Fetch robots.txt
        rp = await self._fetch_robots_txt(robots_url)

        # Cache result (even if None)
        async with self.cache_lock:
            self.robots_cache[robots_url] = rp

        return rp

    async def _fetch_robots_txt(
        self,
        robots_url: str
    ) -> Optional[urllib.robotparser.RobotFileParser]:
        """
        Fetch and parse robots.txt

        Args:
            robots_url: robots.txt URL

        Returns:
            RobotFileParser instance or None if fetch fails
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(robots_url, ssl=False) as response:
                    if response.status == 200:
                        content = await response.text()

                        # Parse robots.txt
                        rp = urllib.robotparser.RobotFileParser()
                        rp.set_url(robots_url)
                        rp.parse(content.splitlines())

                        logger.debug(f"Successfully fetched robots.txt from {robots_url}")
                        return rp

                    elif response.status == 404:
                        # No robots.txt exists
                        logger.debug(f"No robots.txt at {robots_url} (404)")
                        return None

                    else:
                        logger.warning(f"Failed to fetch robots.txt from {robots_url}: {response.status}")
                        return None

        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching robots.txt from {robots_url}")
            return None

        except Exception as e:
            logger.warning(f"Error fetching robots.txt from {robots_url}: {e}")
            return None

    def clear_cache(self, domain: Optional[str] = None):
        """
        Clear robots.txt cache

        Args:
            domain: Specific domain to clear (None = clear all)
        """
        if domain:
            robots_urls = [
                key for key in self.robots_cache.keys()
                if domain in key
            ]
            for url in robots_urls:
                self.robots_cache.pop(url, None)
            logger.info(f"Cleared robots.txt cache for {domain}")
        else:
            self.robots_cache.clear()
            logger.info("Cleared all robots.txt cache")
