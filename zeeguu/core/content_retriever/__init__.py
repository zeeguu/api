from zeeguu.core.content_cleaning import cleanup_text, cleanup_text_w_content_removed


def download_and_parse(url):
    from .parse_with_readability_server import download_and_parse as _download_and_parse

    np_article = _download_and_parse(url)
    np_article.text = cleanup_text(np_article.text)

    return np_article


def download_and_parse_with_remove_sents(url):
    from .parse_with_readability_server import download_and_parse as _download_and_parse

    np_article = _download_and_parse(url)
    np_article.text, sents_rem_counter = cleanup_text_w_content_removed(np_article.text)

    return np_article, sents_rem_counter
