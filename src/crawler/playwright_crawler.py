from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Error as PlaywrightError
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
import logging
from src.core.config import settings
from src.core.exceptions import PlaywrightException, CrawlTimeoutException

logger = logging.getLogger(__name__)


class PlaywrightCrawler:
    """Browser automation crawler using Playwright"""

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None

    async def __aenter__(self):
        """Async context manager entry - initialize Playwright"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',  # Critical for Docker
                    '--disable-blink-features=AutomationControlled',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
                ]
            )
            logger.info("Playwright browser launched successfully")
            return self
        except Exception as e:
            logger.error(f"Failed to launch Playwright browser: {str(e)}")
            raise PlaywrightException(f"Failed to initialize Playwright: {str(e)}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup"""
        if self.browser:
            await self.browser.close()
            logger.debug("Browser closed")
        if self.playwright:
            await self.playwright.stop()
            logger.debug("Playwright stopped")

    @asynccontextmanager
    async def get_context(self) -> BrowserContext:
        """Get a new isolated browser context"""
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=settings.CRAWLER_USER_AGENT,
            ignore_https_errors=True,  # Handle sites with SSL issues
            java_script_enabled=True
        )
        try:
            yield context
        finally:
            await context.close()

    async def crawl_page(
        self,
        url: str,
        timeout: int = None
    ) -> Dict:
        """
        Crawl a single page and extract all links

        Args:
            url: URL to crawl
            timeout: Timeout in milliseconds (default from settings)

        Returns:
            {
                'url': final URL after redirects,
                'status': HTTP status code,
                'title': page title,
                'links': [{'href': url, 'text': anchor_text, 'rel': rel_attr}, ...],
                'error': error message if any,
                'content_type': content type header
            }
        """
        if timeout is None:
            timeout = settings.CRAWLER_DEFAULT_TIMEOUT * 1000  # Convert to ms

        async with self.get_context() as context:
            page = await context.new_page()

            try:
                # Navigate to page with network idle wait
                response = await page.goto(
                    url,
                    wait_until='networkidle',
                    timeout=timeout
                )

                if not response:
                    return {
                        'url': url,
                        'status': None,
                        'title': None,
                        'links': [],
                        'error': 'No response received',
                        'content_type': None
                    }

                # Get page metadata
                title = await page.title()
                final_url = page.url
                status = response.status
                content_type = response.headers.get('content-type', '')

                # Extract all links using JavaScript
                links = await page.evaluate('''() => {
                    const anchors = document.querySelectorAll('a[href]');
                    return Array.from(anchors).map(a => ({
                        href: a.href,
                        text: a.textContent.trim().substring(0, 200),  // Limit text length
                        rel: a.rel || ''
                    })).filter(link => link.href);  // Filter out empty hrefs
                }''')

                logger.info(
                    f"Successfully crawled {url}",
                    extra={
                        'url': url,
                        'final_url': final_url,
                        'status': status,
                        'links_found': len(links)
                    }
                )

                return {
                    'url': final_url,
                    'status': status,
                    'title': title,
                    'links': links,
                    'error': None,
                    'content_type': content_type
                }

            except PlaywrightError as e:
                error_msg = str(e)
                if 'Timeout' in error_msg:
                    logger.warning(f"Timeout crawling {url}: {error_msg}")
                    raise CrawlTimeoutException(f"Timeout crawling {url}")
                else:
                    logger.error(f"Playwright error crawling {url}: {error_msg}")
                    return {
                        'url': url,
                        'status': None,
                        'title': None,
                        'links': [],
                        'error': error_msg,
                        'content_type': None
                    }

            except Exception as e:
                logger.error(f"Unexpected error crawling {url}: {str(e)}")
                return {
                    'url': url,
                    'status': None,
                    'title': None,
                    'links': [],
                    'error': str(e),
                    'content_type': None
                }

            finally:
                await page.close()

    async def check_page_status(self, url: str, timeout: int = 10000) -> Dict:
        """
        Quick check of page status without full rendering

        Args:
            url: URL to check
            timeout: Timeout in milliseconds

        Returns:
            {'status': HTTP status code, 'error': error message if any}
        """
        async with self.get_context() as context:
            page = await context.new_page()

            try:
                response = await page.goto(url, timeout=timeout, wait_until='domcontentloaded')

                return {
                    'status': response.status if response else None,
                    'error': None if response else 'No response'
                }

            except Exception as e:
                return {
                    'status': None,
                    'error': str(e)
                }

            finally:
                await page.close()
