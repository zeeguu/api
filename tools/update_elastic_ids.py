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
from zeeguu.core.elastic.settings import ES_ZINDEX, ES_CONN_STRING
from tqdm import tqdm

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
DELETE_INDEX = False
INDEX_WITH_TOPIC_ONLY = True
TOTAL_ITEMS = 1000
ITERATION_STEP = 100

print(ES_CONN_STRING)
es = Elasticsearch(ES_CONN_STRING)
db_session = zeeguu.core.model.db.session
print(es.info())


def main():

    def fetch_articles_by_id(id_list):
        for i in id_list:
            try:
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

    es_query = {"query": {"match_all": {}}}
    ids_in_es = [int(hit["_id"]) for hit in scan(es, index=ES_ZINDEX, query=es_query)]
    total_added = 0
    errors_encountered = []
    print(f"""Total articles in ES: {len(ids_in_es)}""")
    for i_start in tqdm(range(0, len(ids_in_es), ITERATION_STEP)):
        res_bulk, error_bulk = bulk(
            es,
            gen_docs(
                fetch_articles_by_id(ids_in_es[i_start : i_start + ITERATION_STEP])
            ),
            raise_on_error=False,
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
    print(f"Process took: {end - start}")
