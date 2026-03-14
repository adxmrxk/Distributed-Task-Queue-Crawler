from typing import List, Dict
from urllib.parse import urljoin, urlparse
import logging
from src.utils.url_utils import normalize_url, validate_url, is_same_domain

logger = logging.getLogger(__name__)


class LinkExtractor:
    """Extract and process links from crawled pages"""

    @staticmethod
    def extract_links(
        base_url: str,
        links: List[Dict],
        same_domain_only: bool = False
    ) -> Dict[str, List[str]]:
        """
        Extract and categorize links from a page

        Args:
            base_url: Base URL of the page
            links: List of link dictionaries from Playwright
            same_domain_only: Only return same-domain links

        Returns:
            {
                'internal': [list of internal URLs],
                'external': [list of external URLs],
                'invalid': [list of invalid URLs]
            }
        """
        internal = []
        external = []
        invalid = []

        seen = set()  # Deduplicate

        for link in links:
            try:
                href = link.get('href', '').strip()
                if not href:
                    continue

                # Resolve relative URLs
                absolute_url = urljoin(base_url, href)

                # Skip non-HTTP(S) URLs
                if not absolute_url.startswith(('http://', 'https://')):
                    continue

                # Validate URL
                if not validate_url(absolute_url):
                    invalid.append(absolute_url)
                    continue

                # Normalize URL for deduplication
                try:
                    normalized = normalize_url(absolute_url)
                except Exception as e:
                    logger.debug(f"Failed to normalize {absolute_url}: {e}")
                    invalid.append(absolute_url)
                    continue

                # Skip duplicates
                if normalized in seen:
                    continue
                seen.add(normalized)

                # Categorize
                if is_same_domain(base_url, normalized):
                    internal.append(normalized)
                else:
                    if not same_domain_only:
                        external.append(normalized)

            except Exception as e:
                logger.debug(f"Error processing link {link}: {e}")
                invalid.append(str(link.get('href', '')))

        logger.debug(
            f"Extracted links from {base_url}: "
            f"{len(internal)} internal, {len(external)} external, {len(invalid)} invalid"
        )

        return {
            'internal': internal,
            'external': external,
            'invalid': invalid
        }

    @staticmethod
    def filter_links(
        links: List[str],
        exclude_patterns: List[str] = None,
        include_patterns: List[str] = None,
        max_depth: int = None
    ) -> List[str]:
        """
        Filter links based on patterns and constraints

        Args:
            links: List of URLs to filter
            exclude_patterns: Patterns to exclude (e.g., ['.pdf', '.zip'])
            include_patterns: Patterns to include (e.g., ['/blog/'])
            max_depth: Maximum URL path depth

        Returns:
            Filtered list of URLs
        """
        filtered = []

        for link in links:
            try:
                # Check exclude patterns
                if exclude_patterns:
                    if any(pattern in link for pattern in exclude_patterns):
                        continue

                # Check include patterns
                if include_patterns:
                    if not any(pattern in link for pattern in include_patterns):
                        continue

                # Check depth
                if max_depth is not None:
                    parsed = urlparse(link)
                    path_depth = len([p for p in parsed.path.split('/') if p])
                    if path_depth > max_depth:
                        continue

                filtered.append(link)

            except Exception as e:
                logger.debug(f"Error filtering link {link}: {e}")

        return filtered
