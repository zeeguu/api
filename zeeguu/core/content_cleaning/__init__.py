from zeeguu.core.content_cleaning.content_cleaner import (
    cleanup_non_content_bits,
    cleanup_non_content_bits_w_crawl_report,
)
from zeeguu.core.content_cleaning.unicode_normalization import (
    flatten_composed_unicode_characters,
)


def cleanup_text(text):
    result = cleanup_non_content_bits(text)
    return flatten_composed_unicode_characters(result)


def cleanup_text_w_crawl_report(text, crawl_report, feed, url):
    result = cleanup_non_content_bits_w_crawl_report(text, crawl_report, feed, url)
    return flatten_composed_unicode_characters(result)
