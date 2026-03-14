from urllib.parse import urlparse, urlunparse, urljoin
from typing import Optional
import re
from src.core.exceptions import InvalidURLException


def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent comparison and storage

    - Converts to lowercase
    - Removes fragments (#)
    - Removes default ports (80, 443)
    - Sorts query parameters
    - Removes trailing slashes (except root)
    """
    try:
        parsed = urlparse(url.strip())

        # Validate scheme
        if parsed.scheme not in ('http', 'https'):
            raise InvalidURLException(f"Invalid URL scheme: {parsed.scheme}")

        # Normalize netloc (lowercase)
        netloc = parsed.netloc.lower()

        # Remove default ports
        if netloc.endswith(':80') and parsed.scheme == 'http':
            netloc = netloc[:-3]
        elif netloc.endswith(':443') and parsed.scheme == 'https':
            netloc = netloc[:-4]

        # Normalize path (remove trailing slash except for root)
        path = parsed.path
        if path != '/' and path.endswith('/'):
            path = path[:-1]
        if not path:
            path = '/'

        # Sort query parameters for consistency
        query = parsed.query
        if query:
            params = sorted(query.split('&'))
            query = '&'.join(params)

        # Rebuild URL without fragment
        normalized = urlunparse((
            parsed.scheme,
            netloc,
            path,
            parsed.params,
            query,
            ''  # Remove fragment
        ))

        return normalized
    except Exception as e:
        raise InvalidURLException(f"Failed to normalize URL '{url}': {str(e)}")


def validate_url(url: str) -> bool:
    """Validate if a string is a valid HTTP/HTTPS URL"""
    try:
        parsed = urlparse(url)
        return all([
            parsed.scheme in ('http', 'https'),
            parsed.netloc,
            len(url) <= 2048  # Max URL length
        ])
    except Exception:
        return False


def is_same_domain(base_url: str, target_url: str) -> bool:
    """Check if two URLs belong to the same domain"""
    try:
        base_parsed = urlparse(base_url)
        target_parsed = urlparse(target_url)

        return base_parsed.netloc.lower() == target_parsed.netloc.lower()
    except Exception:
        return False


def get_domain(url: str) -> Optional[str]:
    """Extract domain (netloc) from URL"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return None


def get_base_url(url: str) -> Optional[str]:
    """Get base URL (scheme + netloc)"""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return None


def resolve_relative_url(base_url: str, relative_url: str) -> str:
    """Resolve a relative URL against a base URL"""
    try:
        return urljoin(base_url, relative_url)
    except Exception as e:
        raise InvalidURLException(f"Failed to resolve relative URL: {str(e)}")


def is_valid_http_url(url: str) -> bool:
    """Comprehensive URL validation with regex"""
    regex = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP address
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return bool(regex.match(url))
