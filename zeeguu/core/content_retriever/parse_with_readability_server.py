import json

import newspaper
from langdetect import detect
import requests

from zeeguu.core.content_retriever.crawler_exceptions import (
    FailedToParseWithReadabilityServer,
)

READABILITY_SERVER_CLEANUP_URI = "http://readability_server:3456/cleanup?url="
READABILITY_SERVER_CLEANUP_POST_URI = "http://readability_server:3456/cleanup"
TIMEOUT_SECONDS = 20


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
    np_article = newspaper.Article(url=url)

    if html_content:
        # Use provided HTML content instead of downloading
        np_article.set_html(html_content)
    else:
        # Download HTML from URL
        np_article.download()

    np_article.parse()

    if np_article.text == "":
        # raise Exception("Newspaper got empty article from: " + url)
        np_article.text = "N/A"
        # this is a temporary solution for allowing translations
        # on pages that do not have "articles" downloadable by newspaper.

    # Call readability server - use POST if we have HTML content, GET otherwise
    if html_content:
        # POST endpoint with HTML content
        result = requests.post(
            READABILITY_SERVER_CLEANUP_POST_URI,
            json={"url": url, "htmlContent": html_content},
            timeout=request_timeout
        )
    else:
        # GET endpoint - server will fetch the URL
        result = requests.get(READABILITY_SERVER_CLEANUP_URI + url, timeout=request_timeout)

    if result.status_code == 500:
        raise FailedToParseWithReadabilityServer(result.text)

    result_dict = json.loads(result.text)
    np_article.text = result_dict["text"]
    np_article.htmlContent = result_dict["html"]
    
    # Use title from readability server if available and better than newspaper's
    if "title" in result_dict and result_dict["title"]:
        if not np_article.title or len(result_dict["title"]) > len(np_article.title):
            np_article.title = result_dict["title"]
    
    # Update other metadata if available
    if "byline" in result_dict and result_dict["byline"]:
        if not np_article.authors:
            np_article.authors = [result_dict["byline"]]

    if np_article.meta_lang == "":
        np_article.meta_lang = detect(np_article.text)

    # Other relevant attributes: title, text, summary, authors
    return np_article
