import aiohttp
import asyncio
from typing import Tuple, Optional
import logging
from src.core.constants import LinkErrorType
from src.core.config import settings

logger = logging.getLogger(__name__)


class LinkValidator:
    """Lightweight link validation using HEAD/GET requests"""

    def __init__(self, timeout: int = None):
        self.timeout = timeout or settings.CRAWLER_DEFAULT_TIMEOUT
        self.client_timeout = aiohttp.ClientTimeout(total=self.timeout)

    async def check_link(
        self,
        url: str
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[str]]:
        """
        Check if a link is valid using HTTP requests

        Args:
            url: URL to check

        Returns:
            Tuple of (is_valid, status_code, error_type, error_message)
        """
        try:
            async with aiohttp.ClientSession(timeout=self.client_timeout) as session:
                # Try HEAD request first (faster, doesn't download body)
                try:
                    async with session.head(
                        url,
                        allow_redirects=True,
                        ssl=False  # Don't verify SSL for broken sites
                    ) as response:
                        status = response.status

                        # Success
                        if status < 400:
                            logger.debug(f"Link valid: {url} (status {status})")
                            return True, status, None, None

                        # Method not allowed - fallback to GET
                        if status == 405:
                            return await self._check_with_get(session, url)

                        # Client or server error
                        logger.debug(f"Link broken: {url} (status {status})")
                        return (
                            False,
                            status,
                            LinkErrorType.HTTP_ERROR.value,
                            f"HTTP {status}"
                        )

                except aiohttp.ClientResponseError as e:
                    # HEAD failed, try GET
                    if e.status == 405:
                        return await self._check_with_get(session, url)
                    raise

        except asyncio.TimeoutError:
            logger.warning(f"Timeout checking link: {url}")
            return False, None, LinkErrorType.TIMEOUT.value, "Request timeout"

        except aiohttp.ClientConnectorError as e:
            error_msg = str(e)
            if "Name or service not known" in error_msg or "getaddrinfo failed" in error_msg:
                logger.warning(f"DNS error for {url}: {error_msg}")
                return False, None, LinkErrorType.DNS_ERROR.value, "DNS resolution failed"
            logger.warning(f"Connection error for {url}: {error_msg}")
            return False, None, LinkErrorType.CONNECTION_ERROR.value, str(e)

        except aiohttp.ClientSSLError as e:
            logger.warning(f"SSL error for {url}: {str(e)}")
            return False, None, LinkErrorType.SSL_ERROR.value, str(e)

        except aiohttp.InvalidURL as e:
            logger.warning(f"Invalid URL: {url}")
            return False, None, LinkErrorType.INVALID_URL.value, str(e)

        except Exception as e:
            logger.error(f"Unexpected error checking {url}: {str(e)}")
            return False, None, LinkErrorType.CONNECTION_ERROR.value, str(e)

    async def _check_with_get(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[str]]:
        """
        Fallback to GET request if HEAD fails

        Args:
            session: aiohttp session
            url: URL to check

        Returns:
            Tuple of (is_valid, status_code, error_type, error_message)
        """
        try:
            async with session.get(
                url,
                allow_redirects=True,
                ssl=False
            ) as response:
                status = response.status

                if status < 400:
                    logger.debug(f"Link valid (GET): {url} (status {status})")
                    return True, status, None, None
                else:
                    logger.debug(f"Link broken (GET): {url} (status {status})")
                    return (
                        False,
                        status,
                        LinkErrorType.HTTP_ERROR.value,
                        f"HTTP {status}"
                    )

        except Exception as e:
            logger.error(f"GET request failed for {url}: {str(e)}")
            return False, None, LinkErrorType.CONNECTION_ERROR.value, str(e)

    async def check_multiple_links(
        self,
        urls: list[str],
        max_concurrent: int = 10
    ) -> dict[str, Tuple[bool, Optional[int], Optional[str], Optional[str]]]:
        """
        Check multiple links concurrently

        Args:
            urls: List of URLs to check
            max_concurrent: Maximum concurrent requests

        Returns:
            Dictionary mapping URL to validation result
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_with_semaphore(url):
            async with semaphore:
                result = await self.check_link(url)
                return url, result

        tasks = [check_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            url: result if not isinstance(result, Exception) else (False, None, LinkErrorType.CONNECTION_ERROR.value, str(result))
            for url, result in results
            if not isinstance((url, result), Exception)
        }
