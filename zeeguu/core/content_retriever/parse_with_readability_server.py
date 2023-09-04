import newspaper
from langdetect import detect
import requests

READABILITY_SERVER_CLEANUP_URI = "http://16.171.148.98:3000/plain_text"


def download_and_parse(url):
    parsed = newspaper.Article(url=url)
    parsed.download()
    parsed.parse()

    if parsed.text == "":
        # raise Exception("Newspaper got empty article from: " + url)
        parsed.text = "N/A"
        # this is a temporary solution for allowing translations
        # on pages that do not have "articles" downloadable by newspaper.

    result = requests.get(READABILITY_SERVER_CLEANUP_URI + "?url=" + url)
    parsed.text = result.text

    if parsed.meta_lang == "":
        parsed.meta_lang = detect(parsed.text)

    # Other relevant attributes: title, text, summary, authors
    return parsed
