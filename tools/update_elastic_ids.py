# coding=utf-8
from zeeguu.core.elastic.indexing import (
    update_article_ids_in_es_for_bulk,
)
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, scan
import zeeguu.core
from zeeguu.core.model.article import Article
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.app import create_app
from zeeguu.core.elastic.settings import ES_ZINDEX, ES_CONN_STRING
from tqdm import tqdm

app = create_app()
app.app_context().push()

ITERATION_STEP = 1000

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
                yield update_article_ids_in_es_for_bulk(article)
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
