"""Whole site sections that are never articles are dropped by URL, before the
download (SOURCE_URL_FILTERS in article_downloader)."""
from zeeguu.core.content_retriever.article_downloader import (
    should_filter_by_source_keywords,
)


def test_a_chip_software_page_is_filtered():
    url = "https://www.chip.de/download/macos-apps/franz-fuer-macos_f9760d0e-6e2b-4076-9fa5-c1c1cdc1cb4b.html"
    should_filter, reason = should_filter_by_source_keywords(url, "Franz für macOS")
    assert should_filter
    assert "/download/" in reason


def test_a_chip_news_article_is_not():
    url = "https://www.chip.de/news/handy/iphone-18-pro-display_123.html"
    assert not should_filter_by_source_keywords(url, "iPhone 18 Pro")[0]


def test_the_path_rule_is_scoped_to_its_domain():
    url = "https://www.example.com/download/some-report.html"
    assert not should_filter_by_source_keywords(url, "Some report")[0]
