import newspaper
from langdetect import detect


def download_and_parse(url, html_content=None):
    """
    Parse article using newspaper3k.

    Args:
        url: Article URL
        html_content: Optional pre-fetched HTML content. If provided, skip download.
    """
    parsed = newspaper.Article(url=url)

    if html_content:
        # Use provided HTML content instead of downloading
        parsed.set_html(html_content)
    else:
        # Download HTML from URL
        parsed.download()

    parsed.parse()

    if parsed.text == "":
        # raise Exception("Newspaper got empty article from: " + url)
        parsed.text = "N/A"
        # this is a temporary solution for allowing translations
        # on pages that do not have "articles" downloadable by newspaper.

    if parsed.meta_lang == "":
        try:
            parsed.meta_lang = detect(parsed.text)
        except Exception:
            # langdetect can fail on texts with no features, very short texts, etc.
            # Leave meta_lang empty and let Article.find_or_create handle it
            pass

    # Other relevant attributes: title, text, summary, authors
    return parsed
