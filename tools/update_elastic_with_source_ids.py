# coding=utf-8
from zeeguu.core.elastic.indexing import (
    update_doc_with_source_id,
)
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
import zeeguu.core
from zeeguu.core.model.article import Article
from zeeguu.core.model.video import Video
from datetime import datetime
from zeeguu.api.app import create_app
from zeeguu.core.elastic.settings import ES_ZINDEX, ES_CONN_STRING
from tqdm import tqdm

app = create_app()
app.app_context().push()

print(ES_CONN_STRING)
es = Elasticsearch(ES_CONN_STRING)
db_session = zeeguu.core.model.db.session
print(es.info())


def main():

    es_query = {"query": {"match_all": {}}}
    total_documents = es.count(index=ES_ZINDEX)["count"]
    print(f"""Total articles in ES: {total_documents}""")
    for hit in tqdm(scan(es, index=ES_ZINDEX, query=es_query), total=total_documents):
        hit_data = hit["_source"]
        res = None
        if "video_id" in hit_data:
            source_id = Video.find_by_id(hit_data["video_id"]).source_id
            if source_id:
                res = update_doc_with_source_id(hit, source_id)
            else:
                print(f"Video with id {hit_data['video_id']} not found in DB")
        elif "article_id" in hit_data:
            source_id = Article.find_by_id(hit_data["article_id"]).source_id
            if source_id:
                res = update_doc_with_source_id(hit, source_id)
            else:
                print(f"Article with id {hit_data['article_id']} not found in DB")


if __name__ == "__main__":
    start = datetime.now()
    print(f"started at: {start}")
    main()
    end = datetime.now()
    print(f"ended at: {end}")
    print(f"Process took: {end - start}")
