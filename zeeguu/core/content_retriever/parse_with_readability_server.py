import newspaper
from langdetect import detect
import requests

READABILITY_SERVER_CLEANUP_URI = "http://16.171.148.98:3000/plain_text?url="
TIMEOUT_SECONDS = 60  # 1 Minutes Timeout ?


def download_and_parse(url, request_timeout=TIMEOUT_SECONDS):
    # This code will be run twice when using a newspaper source
    # Maybe add a flag to avoid running this if the feed type == newspaper
    parsed = newspaper.Article(url=url)
    print("newspaper.download for " + url)
    parsed.download()
    parsed.parse()

    if parsed.text == "":
        # raise Exception("Newspaper got empty article from: " + url)
        parsed.text = "N/A"
        # this is a temporary solution for allowing translations
        # on pages that do not have "articles" downloadable by newspaper.

    # Is there a timeout?
    # When using the tool to download artiles, this got stuck
    # in this line of code.
    result = requests.get(READABILITY_SERVER_CLEANUP_URI + url, timeout=request_timeout)
    parsed.text = result.text

    if parsed.meta_lang == "":
        parsed.meta_lang = detect(parsed.text)

    # Other relevant attributes: title, text, summary, authors
    return parsed
