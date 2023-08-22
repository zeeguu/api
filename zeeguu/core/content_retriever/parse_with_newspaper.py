import newspaper
from langdetect import detect


def download_and_parse(url):
    parsed = newspaper.Article(url=url)
    parsed.download()
    parsed.parse()

    if parsed.text == "":
        # raise Exception("Newspaper got empty article from: " + url)
        parsed.text = "N/A"
        # this is a temporary solution for allowing translations
        # on pages that do not have "articles" downloadable by newspaper.

    if parsed.meta_lang == "":
        parsed.meta_lang = detect(parsed.text)

    # Other relevant attributes: title, text, summary, authors
    return parsed
