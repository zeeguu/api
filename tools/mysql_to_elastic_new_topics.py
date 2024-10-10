# coding=utf-8
from zeeguu.core.elastic.indexing import (
    create_or_update,
    document_from_article,
    create_or_update_bulk_docs,
)
from sqlalchemy import func
from elasticsearch import Elasticsearch, helpers
from elasticsearch.helpers import bulk
import zeeguu.core
from zeeguu.core.model import Article
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.app import create_app

from zeeguu.core.model import Topic, NewArticleTopicMap
from zeeguu.core.model.article import article_topic_map
from zeeguu.core.elastic.settings import ES_ZINDEX, ES_CONN_STRING
import numpy as np
from tqdm import tqdm

app = create_app()
app.app_context().push()

DELETE_INDEX = False
TOTAL_ITEMS = 1000
ITERATION_STEP = 10

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


def main():
    if DELETE_INDEX:
        try:
            es.options(ignore_status=[400, 404]).indices.delete(index="zeeguu")
            print("Deleted index 'zeeguu'!")
        except Exception as e:
            print(f"Failed to delete: {e}")

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

    # Sample Articles that have topics assigned and are not inferred
    sample_ids = np.array(
        [
            a_id[0]
            for a_id in db_session.query(Article.id)
            .join(NewArticleTopicMap)
            .filter(Article.language_id == 2)
            .filter(NewArticleTopicMap.origin_type != 3)
            .all()
        ]
    )
    if len(sample_ids) == 0:
        print("No articles found! Exiting...")
        return
    sample_ids_no_in_es = list(
        filter(lambda x: not es.exists(index=ES_ZINDEX, id=x), sample_ids)
    )
    print("Total articles missing: ", len(sample_ids_no_in_es))

    # I noticed that if a document is not added then it won't let me query the ES search.
    total_added = 0
    sampled_ids = np.random.choice(
        sample_ids_no_in_es, min(TOTAL_ITEMS, len(sample_ids_no_in_es)), replace=False
    )
    for i_start in tqdm(range(0, TOTAL_ITEMS, ITERATION_STEP)):
        sub_sample = sampled_ids[i_start : i_start + ITERATION_STEP]
        try:
            res, _ = bulk(es, gen_docs(fetch_articles_by_id(sub_sample)))
            total_added += res
        except helpers.BulkIndexError:
            print("-- WARNING, at least one document failed to index.")
    print(f"Total articles added: {total_added}")


if __name__ == "__main__":

    print("waiting for the ES process to boot up")
    start = datetime.now()
    print(f"started at: {start}")
    main()
    end = datetime.now()
    print(f"ended at: {end}")
    print(f"Process took: {end-start}")
