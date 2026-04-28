"""Unit tests for src/utils/url_utils.py"""
import pytest
from src.utils.url_utils import (
    normalize_url,
    validate_url,
    is_same_domain,
    get_domain,
    get_base_url,
    resolve_relative_url,
    is_valid_http_url,
)
from src.core.exceptions import InvalidURLException


# ---------------------------------------------------------------------------
# normalize_url
# ---------------------------------------------------------------------------

class TestNormalizeUrl:
    def test_strips_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_removes_trailing_slash(self):
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_preserves_root_slash(self):
        result = normalize_url("https://example.com/")
        assert result == "https://example.com/"

    def test_lowercases_domain(self):
        assert normalize_url("https://EXAMPLE.COM/path") == "https://example.com/path"

    def test_removes_default_http_port(self):
        assert normalize_url("http://example.com:80/page") == "http://example.com/page"

    def test_removes_default_https_port(self):
        assert normalize_url("https://example.com:443/page") == "https://example.com/page"

    def test_keeps_non_default_port(self):
        result = normalize_url("https://example.com:8443/page")
        assert ":8443" in result

    def test_sorts_query_params(self):
        result = normalize_url("https://example.com/?z=1&a=2")
        assert result == "https://example.com/?a=2&z=1"

    def test_strips_leading_whitespace(self):
        result = normalize_url("  https://example.com/page  ")
        assert result == "https://example.com/page"

    def test_raises_on_non_http_scheme(self):
        with pytest.raises(InvalidURLException):
            normalize_url("ftp://example.com/file")

    def test_raises_on_empty_string(self):
        with pytest.raises(InvalidURLException):
            normalize_url("")

    def test_https_preserved(self):
        result = normalize_url("https://example.com/path")
        assert result.startswith("https://")

    def test_path_without_trailing_slash(self):
        result = normalize_url("https://example.com/a/b/c")
        assert result == "https://example.com/a/b/c"


# ---------------------------------------------------------------------------
# validate_url
# ---------------------------------------------------------------------------

class TestValidateUrl:
    def test_valid_http(self):
        assert validate_url("http://example.com") is True

    def test_valid_https(self):
        assert validate_url("https://example.com/path?q=1") is True

    def test_rejects_ftp(self):
        assert validate_url("ftp://example.com") is False

    def test_rejects_empty(self):
        assert validate_url("") is False

    def test_rejects_no_scheme(self):
        assert validate_url("example.com") is False

    def test_rejects_too_long(self):
        long_url = "https://example.com/" + "a" * 2048
        assert validate_url(long_url) is False

    def test_valid_with_port(self):
        assert validate_url("http://localhost:8000/api") is True


# ---------------------------------------------------------------------------
# is_same_domain
# ---------------------------------------------------------------------------

class TestIsSameDomain:
    def test_same_domain(self):
        assert is_same_domain("https://example.com/a", "https://example.com/b") is True

    def test_different_domains(self):
        assert is_same_domain("https://example.com", "https://other.com") is False

    def test_case_insensitive(self):
        assert is_same_domain("https://EXAMPLE.COM/a", "https://example.com/b") is True

    def test_different_subdomains(self):
        assert is_same_domain("https://www.example.com", "https://api.example.com") is False

    def test_same_domain_different_schemes(self):
        # Domain match ignores scheme — only netloc is compared
        assert is_same_domain("http://example.com", "https://example.com") is True


# ---------------------------------------------------------------------------
# get_domain
# ---------------------------------------------------------------------------

class TestGetDomain:
    def test_extracts_domain(self):
        assert get_domain("https://example.com/path") == "example.com"

    def test_lowercases(self):
        assert get_domain("https://EXAMPLE.COM/") == "example.com"

    def test_includes_port(self):
        assert get_domain("https://example.com:8443/path") == "example.com:8443"

    def test_returns_none_on_error(self):
        # Malformed input that still parses but has no netloc
        result = get_domain("not-a-url")
        assert result == "" or result is None or result == "not-a-url"


# ---------------------------------------------------------------------------
# get_base_url
# ---------------------------------------------------------------------------

class TestGetBaseUrl:
    def test_returns_scheme_and_host(self):
        assert get_base_url("https://example.com/path?q=1") == "https://example.com"

    def test_http(self):
        assert get_base_url("http://example.com/page") == "http://example.com"

    def test_with_port(self):
        assert get_base_url("http://localhost:8000/api/v1") == "http://localhost:8000"


# ---------------------------------------------------------------------------
# resolve_relative_url
# ---------------------------------------------------------------------------

class TestResolveRelativeUrl:
    def test_absolute_path(self):
        result = resolve_relative_url("https://example.com/blog/post", "/about")
        assert result == "https://example.com/about"

    def test_relative_path(self):
        result = resolve_relative_url("https://example.com/blog/", "post.html")
        assert result == "https://example.com/blog/post.html"

    def test_full_url_unchanged(self):
        result = resolve_relative_url("https://example.com/blog", "https://other.com/page")
        assert result == "https://other.com/page"

    def test_fragment_link(self):
        result = resolve_relative_url("https://example.com/page", "#section")
        assert "example.com" in result


# ---------------------------------------------------------------------------
# is_valid_http_url (regex-based)
# ---------------------------------------------------------------------------

class TestIsValidHttpUrl:
    def test_valid_https(self):
        assert is_valid_http_url("https://example.com") is True

    def test_valid_http_with_path(self):
        assert is_valid_http_url("http://example.com/path/to/page") is True

    def test_valid_ip_address(self):
        assert is_valid_http_url("http://192.168.1.1/page") is True

    def test_valid_localhost(self):
        assert is_valid_http_url("http://localhost:8080/api") is True

    def test_rejects_ftp(self):
        assert is_valid_http_url("ftp://example.com") is False

    def test_rejects_plain_string(self):
        assert is_valid_http_url("not-a-url") is False

    def test_valid_with_query_string(self):
        assert is_valid_http_url("https://example.com/search?q=hello&page=2") is True
