import newspaper
from langdetect import detect
from readabilipy import simple_json_from_html_string
import requests


def download_and_parse(url):
    parsed = newspaper.Article(url=url)
    parsed.download()
    parsed.parse()

    req = requests.get(url)
    article = simple_json_from_html_string(req.text, use_readability=True)

    text = ''
    for each in article['plain_text']:
        text += each['text'] + "\n\n"  # convention expected by Zeeguu reader... TODO: change to single newline

    parsed.text = text
    parsed.html = article['content']

    if parsed.meta_lang == "":
        parsed.meta_lang = detect(parsed.text)

    # Other relevant attributes: title, text, summary, authors
    return parsed
