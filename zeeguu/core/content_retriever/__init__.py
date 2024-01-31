from zeeguu.core.content_cleaning import cleanup_text

TIMEOUT_SECONDS = 120

def download_and_parse(url):
    from .parse_with_readability_server import download_and_parse as _download_and_parse
    parsed = _download_and_parse(url, TIMEOUT_SECONDS)
    parsed.text = cleanup_text(parsed.text)

    return parsed
