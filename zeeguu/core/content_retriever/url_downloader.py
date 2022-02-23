import newspaper
from langdetect import detect
import time
from random import randint


def download_url(url, sleep_a_bit):
    art = newspaper.Article(url=url)
    art.download()
    art.parse()

    if art.text == "":
        # raise Exception("Newspaper got empty article from: " + url)
        art.text = "N/A"
        # this is a temporary solution for allowing translations
        # on pages that do not have "articles" downloadable by newspaper.

    if sleep_a_bit:

        print("GOT: " + url)
        sleep_time = randint(3, 33)
        print(f"sleeping for {sleep_time}s... so we don't annoy our friendly servers")
        time.sleep(sleep_time)

    if art.meta_lang == "":
        art.meta_lang = detect(art.text)

    return art.title, art.text, art.summary, art.meta.lang, art.authors
