# coding=utf-8
from zeeguu.core.elastic.indexing import (
    create_or_update_doc_for_bulk,
)
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, scan
import zeeguu.core
from zeeguu.core.model import Article
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.app import create_app
from zeeguu.core.model import ArticleTopicMap
from zeeguu.core.elastic.settings import ES_ZINDEX, ES_CONN_STRING
from zeeguu.core.model.article_topic_map import TopicOriginType
import numpy as np
from tqdm import tqdm
import time

app = create_app()
app.app_context().push()
# First we should only index with topics so we can do
# inference based on the articles that have topics.

# These parameters can be changed based on need.
#   DELETE_INDEX - used to re-index from scratch. Default: False
#   INDEX_WITH_TOPIC_ONLY - determines which articles are indexed. If set to True,
# only the articles which have a topic assigned to them are index. If false, then
# only the articles without the topic will be added. Default: True
#   TOTAL_ITEMS - total items to be indexed, the IDs are sampled and this is used to
# have a variety of different articles in ES. Default: 5000
# NOTE: If you want to index all the articles, you shoud pass a number that's higher
# or equal to the number of articles in the DB
#   ITERATION_STEP - number of articles to index before reporting. Default: 1000
DELETE_INDEX = True
INDEX_WITH_TOPIC_ONLY = True
TOTAL_ITEMS = 10000
ITERATION_STEP = 100

print(ES_CONN_STRING)
es = Elasticsearch(ES_CONN_STRING)
db_session = zeeguu.core.model.db.session
print(es.info())


def main():
    if DELETE_INDEX:
        try:
            es.options(ignore_status=[400, 404], request_timeout=120).indices.delete(
                index=ES_ZINDEX
            )
            print("Deleted index 'zeeguu'!")
        except Exception as e:
            print(f"Failed to delete: {e}")

    def fetch_articles_by_id(id_list):
        for i in id_list:
            try:
                if es.exists(index=ES_ZINDEX, id=i):
                    print(f"Skipped for: '{i}', article already in ES.")
                    continue
                article = Article.find_by_id(i)
                if not article:
                    print(f"Skipped for: '{i}', article not in DB.")
                    continue
                yield article
            except NoResultFound:
                print(f"fail for: '{i}'")
            except Exception as e:
                print(f"fail for: '{i}', {e}")

    def gen_docs(articles_w_topics):
        for article in articles_w_topics:
            try:
                yield create_or_update_doc_for_bulk(article, db_session)
            except Exception as e:
                print(f"fail for: '{article.id}', {e}")

    # Sample Articles that have topics assigned and are not inferred
    if INDEX_WITH_TOPIC_ONLY:
        target_ids = np.array(
            [
                a_id[0]
                for a_id in db_session.query(Article.id)
                .join(ArticleTopicMap)
                .filter(
                    ArticleTopicMap.origin_type != TopicOriginType.INFERRED
                )  # Do not index Inferred topics
                .filter(Article.broken != 1)  # Filter out documents that are broken
                # .filter(Article.language_id == 2) If only one language
                .distinct()
            ]
        )
        print("Got articles with topics, total: ", len(target_ids))
    else:
        articles_with_topic = set(
            [
                art_id_w_topic[0]
                for art_id_w_topic in db_session.query(
                    ArticleTopicMap.article_id
                ).distinct()
            ]
        )
        target_ids = np.array(
            list(
                set([a_id[0] for a_id in db_session.query(Article.id)])
                - articles_with_topic
            )
        )
        print("Got articles without topics, total: ", len(target_ids))

    total_articles_in_es = 0
    if len(target_ids) == 0:
        print("No articles found! Exiting...")
        return
    if es.indices.exists(index=ES_ZINDEX):
        es_query = {"query": {"match_all": {}}}
        ids_in_es = set(
            [int(hit["_id"]) for hit in scan(es, index=ES_ZINDEX, query=es_query)]
        )
        total_articles_in_es = len(ids_in_es)
        target_ids_not_in_es = list(filter(lambda x: x not in ids_in_es, target_ids))
    else:
        # The index was deleted / doesn't exist:
        target_ids_not_in_es = target_ids

    print(f"""Total articles in ES: {total_articles_in_es}""")
    print(f"""Total articles missing: {len(target_ids_not_in_es)}""")
    print(f"""Indexing a total of: {TOTAL_ITEMS}, in batches of: {ITERATION_STEP}""")

    # I noticed that if a document is not added then it won't let me query the ES search.
    total_added = 0
    errors_encountered = []
    final_count_of_articles = min(TOTAL_ITEMS, len(target_ids_not_in_es))
    sampled_ids = np.random.choice(
        target_ids_not_in_es, final_count_of_articles, replace=False
    )
    for i_start in tqdm(range(0, final_count_of_articles, ITERATION_STEP)):
        sub_sample = sampled_ids[i_start : i_start + ITERATION_STEP]
        res_bulk, error_bulk = bulk(
            es, gen_docs(fetch_articles_by_id(sub_sample)), raise_on_error=False
        )
        total_added += res_bulk
        errors_encountered += error_bulk
        total_bulk_errors = len(error_bulk)
        if total_bulk_errors > 0:
            print(f"## Warning, {total_bulk_errors} failed to index. With errors: ")
            print(error_bulk)
        print(f"Batch finished. ADDED:{res_bulk} | ERRORS: {total_bulk_errors}")
    print(errors_encountered)
    print(f"Total articles added: {total_added}")


if __name__ == "__main__":

    start = datetime.now()
    print(f"started at: {start}")
    main()
    end = datetime.now()
    print(f"ended at: {end}")
    print(f"Process took: {end-start}")
