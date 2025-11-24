import json

import newspaper
from langdetect import detect
import requests

from zeeguu.core.content_retriever.crawler_exceptions import (
    FailedToParseWithReadabilityServer,
)

READABILITY_SERVER_CLEANUP_URI = "http://readability_server:3456/cleanup?url="
READABILITY_SERVER_CLEANUP_POST_URI = "http://readability_server:3456/cleanup"
TIMEOUT_SECONDS = 10  # Most articles complete in 1-3s; 10s timeout for problem sites


def download_and_parse(url, html_content=None, request_timeout=TIMEOUT_SECONDS):
    """
    Parse article using readability server and newspaper.

    Args:
        url: Article URL
        html_content: Optional pre-fetched HTML content. If provided, sent to readability server via POST.
        request_timeout: Request timeout in seconds
    """
    # This code will be run twice when using a newspaper source
    # Maybe add a flag to avoid running this if the feed type == newspaper
    # Configure newspaper with timeout
    config = newspaper.Config()
    config.fetch_images = False
    config.request_timeout = 10  # 10 second timeout for downloading
    config.browser_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'  # Modern browser UA

    from zeeguu.logging import log

    np_article = newspaper.Article(url=url, config=config)

    if html_content:
        # Use provided HTML content instead of downloading
        log(f"   Using pre-fetched HTML content")
        np_article.set_html(html_content)
    else:
        # Download HTML from URL
        log(f"   Downloading HTML with newspaper (timeout: {config.request_timeout}s)...")
        try:
            np_article.download()
            log(f"   ✓ HTML downloaded ({len(np_article.html) if np_article.html else 0} bytes)")
        except Exception as e:
            log(f"   ✗ Newspaper download failed: {e}")
            raise

    log(f"   Parsing HTML with newspaper...")
    np_article.parse()
    log(f"   ✓ Parsed ({len(np_article.text)} chars)")

    if np_article.text == "":
        log(f"   ⚠ Newspaper extracted empty text")
        # raise Exception("Newspaper got empty article from: " + url)
        np_article.text = "N/A"
        # this is a temporary solution for allowing translations
        # on pages that do not have "articles" downloadable by newspaper.

    # Call readability server - always use POST with the HTML we already fetched
    log(f"   Calling readability server...")
    import time
    readability_start = time.time()
    result_dict = None  # Initialize to None for exception handling

    try:
        # Use the HTML content we already fetched (either passed in or downloaded by newspaper)
        html_to_send = html_content if html_content else np_article.html

        # POST endpoint with HTML content - avoids double fetch!
        result = requests.post(
            READABILITY_SERVER_CLEANUP_POST_URI,
            json={"url": url, "htmlContent": html_to_send},
            timeout=request_timeout
        )

        readability_duration = time.time() - readability_start
        log(f"   ✓ Readability server responded in {readability_duration:.1f}s (status: {result.status_code})")

        if result.status_code == 500:
            log(f"   ✗ Readability server error: {result.text}")
            raise FailedToParseWithReadabilityServer(result.text)

        result_dict = json.loads(result.text)
        text_length = len(result_dict.get("text", ""))
        html_length = len(result_dict.get("html", ""))
        log(f"   Extracted {text_length} chars of text, {html_length} chars of HTML")

        np_article.text = result_dict["text"]
        np_article.htmlContent = result_dict["html"]
    except requests.exceptions.Timeout:
        log(f"   ✗ Readability server timeout after {request_timeout}s - using newspaper text instead")
        # Fallback: use newspaper's extraction when readability times out
        # This is better than failing completely on complex sites
        np_article.htmlContent = np_article.html
        # Continue with newspaper's already-parsed text (line 52)
    except requests.exceptions.RequestException as e:
        log(f"   ✗ Readability server request failed: {e} - using newspaper text instead")
        # Fallback to newspaper extraction
        np_article.htmlContent = np_article.html

    # Use title from readability server if available and better than newspaper's
    if result_dict and "title" in result_dict and result_dict["title"]:
        if not np_article.title or len(result_dict["title"]) > len(np_article.title):
            np_article.title = result_dict["title"]

    # Update other metadata if available
    if result_dict and "byline" in result_dict and result_dict["byline"]:
        if not np_article.authors:
            np_article.authors = [result_dict["byline"]]

    if np_article.meta_lang == "":
        np_article.meta_lang = detect(np_article.text)

    # Other relevant attributes: title, text, summary, authors
    return np_article
