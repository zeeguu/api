from zeeguu.core.model.article import Article
from zeeguu.core.util import remove_duplciates_keeping_order
from zeeguu.api.app import create_app
import zeeguu.core

from time import time
from tqdm import tqdm
from pprint import pprint
from collections import Counter
import numpy as np
import string

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session


def topic_filter(topic: str) -> bool:
    if topic == "":
        return False
    if topic.isnumeric():
        return False
    if len(topic) > 20:
        return False
    if Counter(topic)["-"] > 2:
        # If there is more than two - in the topic it's probably a title
        return False
    return True


def is_non_word(word: str) -> bool:
    n_upper = 0
    n_numbers = 0
    n_symbols = 0
    n_vowels = 0
    upper_in_middle = False
    for i, c in enumerate(word):
        if c.isupper():
            n_upper += 1
            if not upper_in_middle and i > 0:
                if word[i - 1] != " ":
                    upper_in_middle = True
        if c in string.punctuation:
            n_symbols += 1
        if c in "aeiuo":
            n_vowels += 1
        if c.isnumeric():
            n_numbers += 1
    return (
        n_upper < 2
        and n_symbols == 0
        and n_vowels > 0
        and not upper_in_middle
        and n_numbers == 0
    )


def remove_hyphen(topic: str) -> bool:
    topic = topic
    return topic


def get_topic_keywords_from_article(a: Article):
    try:
        path = str(a.url.path)
        topic_k = filter(topic_filter, path.split("/"))
        topic_k = filter(is_non_word, map(lambda x: x.replace("-", " "), topic_k))
        topic_k = map(lambda x: x.lower().strip(), topic_k)
    except Exception as e:
        print(f"Failed for article '{a.id}', with: '{e}'")
        return None
    return remove_duplciates_keeping_order(topic_k)


def main():
    start = time()
    sample_ids = np.array([a_id[0] for a_id in db_session.query(Article.id).all()])
    # articles = Article.all_younger_than(400)  # Get all articles
    sample_ids = np.random.choice(sample_ids, 2000, replace=False)
    topics_found = set()
    article_topics = {}
    for a_id in tqdm(sample_ids):
        try:
            a = Article.find_by_id(a_id)
            path = str(a.url.path)
            topics = filter(topic_filter, path.split("/"))
            topics = filter(is_non_word, map(lambda x: x.replace("-", " "), topics))
            topics = map(lambda x: x.lower().strip(), topics)
            topics_l = list(topics)
            topics_found.update(topics_l)
            article_topics[a_id] = (
                a.title,
                topics_l,
                a.topics_as_string(),
                path.split("/"),
            )
        except Exception as e:
            print(f"Failed for {a_id}, '{e}'")
    end = time()
    print(f"Process took: {end-start}")
    pprint(topics_found)
    return topics_found, article_topics
