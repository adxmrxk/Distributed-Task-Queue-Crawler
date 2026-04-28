"""Unit tests for src/crawler/link_extractor.py"""
import pytest
from src.crawler.link_extractor import LinkExtractor


def make_links(*hrefs):
    """Helper: build the list-of-dicts format Playwright returns."""
    return [{"href": h} for h in hrefs]


class TestExtractLinks:
    BASE = "https://example.com/blog"

    def test_internal_link(self):
        links = make_links("/about")
        result = LinkExtractor.extract_links(self.BASE, links)
        assert "https://example.com/about" in result["internal"]

    def test_external_link(self):
        links = make_links("https://other.com/page")
        result = LinkExtractor.extract_links(self.BASE, links)
        assert "https://other.com/page" in result["external"]

    def test_relative_link_resolved(self):
        links = make_links("post.html")
        result = LinkExtractor.extract_links("https://example.com/blog/", links)
        assert any("blog/post.html" in u for u in result["internal"])

    def test_empty_href_skipped(self):
        links = make_links("", " ")
        result = LinkExtractor.extract_links(self.BASE, links)
        assert len(result["internal"]) == 0
        assert len(result["external"]) == 0

    def test_deduplication(self):
        links = make_links("/page", "/page", "/page/")
        result = LinkExtractor.extract_links(self.BASE, links)
        # All three normalize to the same URL — should appear only once
        assert len(result["internal"]) == 1

    def test_non_http_scheme_skipped(self):
        links = make_links("mailto:user@example.com", "javascript:void(0)", "tel:123")
        result = LinkExtractor.extract_links(self.BASE, links)
        assert len(result["internal"]) == 0
        assert len(result["external"]) == 0

    def test_same_domain_only_excludes_external(self):
        links = make_links("/internal", "https://other.com/page")
        result = LinkExtractor.extract_links(self.BASE, links, same_domain_only=True)
        assert len(result["external"]) == 0
        assert len(result["internal"]) == 1

    def test_returns_three_keys(self):
        result = LinkExtractor.extract_links(self.BASE, [])
        assert set(result.keys()) == {"internal", "external", "invalid"}

    def test_fragment_stripped_in_normalization(self):
        links = make_links("/page#section")
        result = LinkExtractor.extract_links(self.BASE, links)
        assert all("#" not in u for u in result["internal"])

    def test_mixed_links(self):
        links = make_links("/home", "https://cdn.example.net/img.png", "ftp://old.example.com")
        result = LinkExtractor.extract_links(self.BASE, links)
        assert len(result["internal"]) == 1
        assert len(result["external"]) == 1

    def test_empty_link_list(self):
        result = LinkExtractor.extract_links(self.BASE, [])
        assert result["internal"] == []
        assert result["external"] == []
        assert result["invalid"] == []


class TestFilterLinks:
    LINKS = [
        "https://example.com/blog/post",
        "https://example.com/download/file.pdf",
        "https://example.com/about",
        "https://example.com/a/b/c/deep",
    ]

    def test_exclude_pattern(self):
        result = LinkExtractor.filter_links(self.LINKS, exclude_patterns=[".pdf"])
        assert not any(".pdf" in u for u in result)
        assert len(result) == 3

    def test_include_pattern(self):
        result = LinkExtractor.filter_links(self.LINKS, include_patterns=["/blog/"])
        assert all("/blog/" in u for u in result)
        assert len(result) == 1

    def test_max_depth(self):
        # /a/b/c/deep has path depth 4 — filtered out with max_depth=2
        result = LinkExtractor.filter_links(self.LINKS, max_depth=2)
        assert not any("a/b/c/deep" in u for u in result)

    def test_no_filters_returns_all(self):
        result = LinkExtractor.filter_links(self.LINKS)
        assert result == self.LINKS

    def test_exclude_multiple_patterns(self):
        result = LinkExtractor.filter_links(self.LINKS, exclude_patterns=[".pdf", "/about"])
        assert len(result) == 2

    def test_empty_list(self):
        assert LinkExtractor.filter_links([]) == []

    def test_max_depth_zero_allows_root(self):
        links = ["https://example.com/"]
        result = LinkExtractor.filter_links(links, max_depth=0)
        assert links == result
