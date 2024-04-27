import json

import newspaper
from langdetect import detect
import requests

from zeeguu.core.content_retriever.crawler_exceptions import FailedToParseWithReadabilityServer

READABILITY_SERVER_CLEANUP_URI = "http://readability_server:3456/cleanup?url="
TIMEOUT_SECONDS = 20


def download_and_parse(url, request_timeout=TIMEOUT_SECONDS):
    # This code will be run twice when using a newspaper source
    # Maybe add a flag to avoid running this if the feed type == newspaper
    np_article = newspaper.Article(url=url)
    np_article.download()
    np_article.parse()

    if np_article.text == "":
        # raise Exception("Newspaper got empty article from: " + url)
        np_article.text = "N/A"
        # this is a temporary solution for allowing translations
        # on pages that do not have "articles" downloadable by newspaper.

    # Is there a timeout?
    # When using the tool to download articles, this got stuck
    # in this line of code.
    result = requests.get(READABILITY_SERVER_CLEANUP_URI + url, timeout=request_timeout)
    if result.status_code == 500:
        raise FailedToParseWithReadabilityServer(result.text)

    result_dict = json.loads(result.text)
    np_article.text = result_dict['text']
    np_article.htmlContent = result_dict['html']

    if np_article.meta_lang == "":
        np_article.meta_lang = detect(np_article.text)

    # Other relevant attributes: title, text, summary, authors
    return np_article
