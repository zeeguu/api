# coding=utf-8
from zeeguu.core.elastic.indexing import (
    create_or_update,
    document_from_article,
    create_or_update_bulk_docs,
)
from sqlalchemy import func
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, parallel_bulk
import zeeguu.core
from zeeguu.core.model import Article
import sys
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.app import create_app

from zeeguu.core.model import Topic
from zeeguu.core.model.article import article_topic_map
from zeeguu.core.elastic.settings import ES_ZINDEX, ES_CONN_STRING
import numpy as np

app = create_app()
app.app_context().push()

print(ES_CONN_STRING)
es = Elasticsearch(ES_CONN_STRING)
db_session = zeeguu.core.model.db.session
print(es.info())


def find_topics(article_id, session):
    article_topic = (
        session.query(Topic)
        .join(article_topic_map)
        .filter(article_topic_map.c.article_id == article_id)
    )
    topics = ""
    for t in article_topic:
        topics = topics + str(t.title) + " "

    return topics.rstrip()


def main(starting_index):
    def fetch_articles(max_id, min_id):
        for i in range(max_id, min_id, -1):
            print(f"Article '{i}'")
            try:
                article = Article.find_by_id(i)
                if article:
                    topics = find_topics(article.id, db_session)
                    yield (article, topics)
            except NoResultFound:
                print(f"fail for: '{i}'")
            except Exception as e:
                print(f"fail for: '{i}', {e}")

    def fetch_articles_by_id(id_list):
        for i in id_list:
            try:
                if es.exists(index=ES_ZINDEX, id=i):
                    print(f"Skipped for: '{i}'")
                    continue
                article = Article.find_by_id(i)
                if article:
                    topics = find_topics(article.id, db_session)
                    yield (article, topics)
            except NoResultFound:
                print(f"fail for: '{i}'")
            except Exception as e:
                print(f"fail for: '{i}', {e}")

    def gen_docs(articles_w_topics):
        for article, topics in articles_w_topics:

            try:
                yield create_or_update_bulk_docs(article, db_session, topics)
            except Exception as e:
                print(f"fail for: '{article.id}', {e}")

    # max_id = db_session.query(func.max(Article.id)).first()[0]
    # min_id = db_session.query(func.min(Article.id)).first()[0]
    sample_ids = np.array([a_id[0] for a_id in db_session.query(Article.id).all()])
    total_added = 0
    for i in range(1):
        sub_sample = np.random.choice(sample_ids, 100, replace=False)
        print(f"starting import at: {sub_sample[0]}")
        # print(f"max id in db: {sample_ids}")
        # fetch_db_articles = list(gen_docs(fetch_articles(max_id, max_id - 200)))
        # print(fetch_db_articles[:5])
        # for success, info in parallel_bulk(es, fetch_db_articles):
        #    if not success:
        #        print("A document failed:", info)
        # fetch_db_articles = fetch_articles(max_id, max_id - 200)
        res, _ = bulk(es, gen_docs(fetch_articles_by_id(sub_sample)))
        total_added += res
    print(total_added)


if __name__ == "__main__":

    print("waiting for the ES process to boot up")
    start = datetime.now()
    print(f"started at: {start}")
    starting_index = 0

    if len(sys.argv) > 1:
        starting_index = int(sys.argv[1])

    main(starting_index)
    end = datetime.now()
    print(f"ended at: {end}")
    print(f"Process took: {end-start}")
