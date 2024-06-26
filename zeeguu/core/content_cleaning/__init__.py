from zeeguu.core.content_cleaning.content_cleaner import (
    cleanup_non_content_bits,
    cleanup_non_content_bits_w_sent_count,
)
from zeeguu.core.content_cleaning.unicode_normalization import (
    flatten_composed_unicode_characters,
)


def cleanup_text(text):
    result = cleanup_non_content_bits(text)
    return flatten_composed_unicode_characters(result)


def cleanup_text_w_content_removed(text):
    result, sents_removed = cleanup_non_content_bits_w_sent_count(text)
    return flatten_composed_unicode_characters(result), sents_removed
