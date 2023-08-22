from zeeguu.core.content_cleaning.content_cleaner import cleanup_non_content_bits
from zeeguu.core.content_cleaning.unicode_normalization import (
    flatten_composed_unicode_characters,
)


def cleanup_text(text):
    result = cleanup_non_content_bits(text)
    return flatten_composed_unicode_characters(result)
