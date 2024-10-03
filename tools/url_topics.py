from zeeguu.core.model.article import Article
from zeeguu.core.model.topic_keyword import TopicKeyword
from zeeguu.core.util import remove_duplicates_keeping_order
from zeeguu.api.app import create_app
import zeeguu.core

from time import time
from tqdm import tqdm
from pprint import pprint
from collections import Counter
import numpy as np


app = create_app()
app.app_context().push()
db_session = zeeguu.core.model.db.session


def get_topic_keywords_from_article(a: Article):
    try:
        path = str(a.url.path)
        topic_k = filter(TopicKeyword.topic_filter, path.split("/"))
        topic_k = filter(
            TopicKeyword.is_non_word, map(lambda x: x.replace("-", " "), topic_k)
        )
        topic_k = map(lambda x: x.lower().strip(), topic_k)
    except Exception as e:
        print(f"Failed for article '{a.id}', with: '{e}'")
        return None
    return remove_duplicates_keeping_order(topic_k)


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
            topics = filter(TopicKeyword.topic_filter, path.split("/"))
            topics = filter(
                TopicKeyword.is_non_word, map(lambda x: x.replace("-", " "), topics)
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
