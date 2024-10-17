from zeeguu.core.model.article import Article
from zeeguu.core.model.url_keyword import UrlKeyword
from zeeguu.core.util import remove_duplicates_keeping_order
from zeeguu.api.app import create_app
import zeeguu.core

from time import time
from tqdm import tqdm
from pprint import pprint
from collections import Counter
import numpy as np

"""
    Script to test the is_non_word heuristic to extract url_keywords for topics.

    Samples a number of articles and retrieves the keywords from them. After assingning
    topics to the url_keywords it can also be used in order to validate the mappings
    assinged to each keyword.
"""

app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session


def get_url_keywords_from_article(a: Article):
    try:
        path = str(a.url.path)
        url_keywords = filter(UrlKeyword.topic_filter, path.split("/"))
        url_keywords = filter(
            UrlKeyword.is_non_word, map(lambda x: x.replace("-", " "), url_keywords)
        )
        url_keywords = map(lambda x: x.lower().strip(), url_keywords)
    except Exception as e:
        print(f"Failed for article '{a.id}', with: '{e}'")
        return None
    return remove_duplicates_keeping_order(url_keywords)


def main():
    start = time()
    sample_ids = np.array([a_id[0] for a_id in db_session.query(Article.id).all()])
    sample_ids = np.random.choice(sample_ids, 100, replace=False)
    topics_found = set()
    article_topics = {}
    for a_id in tqdm(sample_ids):
        try:
            a = Article.find_by_id(a_id)
            path = str(a.url.path)
            topics = filter(UrlKeyword.topic_filter, path.split("/"))
            topics = filter(
                UrlKeyword.is_non_word, map(lambda x: x.replace("-", " "), topics)
            )
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
